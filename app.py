import os
import time
import random
import string
import logging
from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from jogo import Jogador, PartidaMultiplayer, Configuracao
from health import register_health_routes

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'jogo_das_palavras_secret')

# Configurações otimizadas para produção
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    ping_timeout=120,
    ping_interval=25,
    logger=False,
    engineio_logger=False
)

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Registrar rotas de health check
register_health_routes(app)

salas = {}

def limpar_salas_inativas():
    """Remove salas inativas (sem jogadores há mais de 1 hora)"""
    tempo_atual = time.time()
    
    salas_para_remover = []
    for codigo, sala in salas.items():
        if 'ultimo_acesso' in sala and (tempo_atual - sala['ultimo_acesso']) > 3600:
            # Remover apenas se não houver jogadores
            if len(sala['players']) == 0:
                salas_para_remover.append(codigo)
                logger.info(f'Sala inativa {codigo} será removida')
    
    for codigo in salas_para_remover:
        del salas[codigo]
        logger.info(f'Sala inativa {codigo} removida')

def verificar_iniciar_jogo(codigo):
    """Verifica se o jogo pode ser iniciado e o inicia se possível"""
    if codigo not in salas:
        logger.warning(f'Tentativa de verificar iniciar jogo em sala inexistente: {codigo}')
        return False
    
    partida = salas[codigo]['partida']
    
    # Verificar se temos pelo menos 2 jogadores
    if len(partida.jogadores) < 2:
        logger.info(f'Sala {codigo}: Aguardando mais jogadores ({len(partida.jogadores)}/2)')
        return False
    
    # Verificar se todos definiram palavras
    todos_prontos = True
    jogadores_sem_palavras = []
    
    for jogador in partida.jogadores:
        if len(jogador.palavras) != partida.config.num_palavras:
            todos_prontos = False
            jogadores_sem_palavras.append(jogador.nome)
    
    logger.info(f'Sala {codigo}: {len(partida.jogadores)} jogadores, todos prontos: {todos_prontos}')
    
    if not todos_prontos:
        logger.info(f'Sala {codigo}: Aguardando palavras de: {", ".join(jogadores_sem_palavras)}')
        return False
    
    # Tudo pronto, iniciar jogo!
    try:
        partida.iniciar_jogo()
        
        estado = partida.get_estado_jogo()
        emit('jogo_iniciado', {
            'msg': 'Todos definiram as palavras! O jogo começou!',
            'estado': estado
        }, room=codigo)
        
        logger.info(f'Jogo iniciado na sala {codigo} com {len(partida.jogadores)} jogadores')
        return True
    except Exception as e:
        logger.error(f'Erro ao iniciar jogo na sala {codigo}: {str(e)}')
        emit('erro', {'msg': f'Erro ao iniciar jogo: {str(e)}'}, room=codigo)
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sala/<codigo>')
def sala_jogo(codigo):
    return render_template('jogo.html')

@socketio.on('connect')
def on_connect():
    logger.info(f'Cliente conectado: {request.sid}')
    # Limpar salas inativas quando alguém se conecta
    limpar_salas_inativas()

@socketio.on('disconnect')
def on_disconnect():
    logger.info(f'Cliente desconectado: {request.sid}')
    
    # Procurar o jogador em todas as salas
    for codigo, sala in list(salas.items()):
        if request.sid in sala['players']:
            nome_jogador = sala['players'][request.sid]
            
            # Remover da lista de players
            del sala['players'][request.sid]
            
            # Se for o criador e não houver outros jogadores, remover a sala
            if request.sid == sala['criador'] and len(sala['players']) == 0:
                del salas[codigo]
                logger.info(f'Sala {codigo} removida após desconexão do criador')
                continue
                
            # Verificar se o jogador ainda tem conexões ativas (em outras abas)
            jogador_ainda_conectado = False
            for sid, nome in sala['players'].items():
                if nome == nome_jogador:
                    jogador_ainda_conectado = True
                    break
                    
            # Se o jogador não estiver mais conectado, remover da partida
            if not jogador_ainda_conectado:
                partida = sala['partida']
                partida.jogadores = [j for j in partida.jogadores if j.nome != nome_jogador]
                
                # Notificar os outros na sala
                emit('jogador_saiu', {
                    'jogador': nome_jogador,
                    'msg': f'{nome_jogador} desconectou-se',
                    'jogadores_restantes': [j.nome for j in partida.jogadores]
                }, room=codigo)
                
                # Reconfigurar alvos se necessário
                if len(partida.jogadores) >= 2:
                    partida._configurar_alvos()
                    
                    # Atualizar estado do jogo para todos
                    estado = partida.get_estado_jogo()
                    emit('estado_atualizado', {'estado': estado}, room=codigo)

@socketio.on('criar_sala')
def criar_sala(data):
    try:
        nome = data.get('nome', '').strip()
        num_palavras = int(data.get('num_palavras', 5))
        # Tornar max_jogadores opcional - usar 8 como padrão (máximo)
        max_jogadores = int(data.get('max_jogadores', 8)) 

        # Validações básicas
        if not nome:
            emit('erro', {'msg': 'Nome é obrigatório'})
            return
        if len(nome) > 20:
            emit('erro', {'msg': 'Nome deve ter no máximo 20 caracteres'})
            return

        # Gera código único de 6 dígitos
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Cria configuração e partida
        config = Configuracao(num_palavras, max_jogadores)
        partida = PartidaMultiplayer(config)
        partida.codigo_sala = codigo

        # Cria jogador e adiciona à partida
        jogador = Jogador(nome, num_palavras)
        partida.adicionar_jogador(jogador)

        # Salva o estado da sala com SID do criador e mapa de players
        salas[codigo] = {
            'partida': partida,
            'criador': request.sid,       # SID do socket que criou
            'players': {                  # map SID → nome
                request.sid: nome
            },
            'palavras': {},               # opcional, se usada
            'ultimo_acesso': time.time()  # timestamp para controle de salas inativas
        }

        # Entra na sala (Socket.IO room)
        join_room(codigo)

        # Emite confirmação de criação, incluindo players e criador
        emit('sala_criada', {
            'codigo': codigo,
            'nome': nome,
            'config': {
                'num_palavras': num_palavras,
                'max_jogadores': max_jogadores
            },
            'players': salas[codigo]['players'],
            'criador': salas[codigo]['criador']
        })

        logger.info(f'Sala {codigo} criada por {nome} ({request.sid}) '
                    f'- {num_palavras} palavras, {max_jogadores} jogadores')

    except Exception as e:
        logger.error(f'Erro ao criar sala: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('entrar_na_sala')
def entrar_na_sala(data):
    try:
        codigo = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()

        if not codigo or codigo not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        if not nome:
            emit('erro', {'msg': 'Nome é obrigatório'})
            return

        partida = salas[codigo]['partida']
        
        # Atualizar timestamp de último acesso
        salas[codigo]['ultimo_acesso'] = time.time()

        # Verifica se o jogador já está na sala (pelo nome)
        jogador_existente = next((j for j in partida.jogadores if j.nome.lower() == nome.lower()), None)

        if not jogador_existente:
            # É um novo jogador
            if len(partida.jogadores) >= partida.config.max_jogadores:
                emit('erro', {'msg': 'A sala está cheia.'})
                return
            
            # Adiciona o novo jogador
            jogador = Jogador(nome, partida.config.num_palavras)
            partida.adicionar_jogador(jogador)
            logger.info(f'Jogador {nome} ({request.sid}) entrou na sala {codigo}')
        else:
            # É o criador ou um jogador reconectando
            logger.info(f'Jogador {nome} ({request.sid}) (re)conectou-se à sala {codigo}')

        join_room(codigo)
        salas[codigo]['players'][request.sid] = nome

        # Notifica todos na sala sobre o estado atual
        jogadores_nomes = [j.nome for j in partida.jogadores]
        emit('jogador_entrou', {
            'jogadores': jogadores_nomes,
            'total': len(partida.jogadores),
            'max': partida.config.max_jogadores
        }, room=codigo)

        # Verificar se o jogo pode ser iniciado (caso todos já tenham definido palavras)
        if len(partida.jogadores) >= 2:
            verificar_iniciar_jogo(codigo)

        # Se a sala estiver cheia, avisa que pode começar
        if len(partida.jogadores) == partida.config.max_jogadores:
            emit('pode_comecar', {
                'msg': 'Sala cheia! Todos devem definir suas palavras.',
                'jogadores': jogadores_nomes,
                'config': {
                    'num_palavras': partida.config.num_palavras,
                    'max_jogadores': partida.config.max_jogadores
                }
            }, room=codigo)
            
        # Se o jogador já tinha enviado palavras, enviar estado atual
        if 'palavras' in salas[codigo] and request.sid in salas[codigo]['palavras']:
            emit('estado_atual', {
                'palavras': {
                    request.sid: salas[codigo]['palavras'][request.sid]
                },
                'config': {
                    'num_palavras': partida.config.num_palavras
                }
            })

    except ValueError as e:
        logger.error(f'Erro ao entrar na sala {codigo}: {str(e)}')
        emit('erro', {'msg': str(e)})
    except Exception as e:
        logger.error(f'Erro ao entrar na sala: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('expulsar_jogador')
def expulsar_jogador(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome_alvo = data.get('nome', '').strip()
        
        if not sala or sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
            
        criador_sid = salas[sala]['criador']
        
        # Só o criador pode expulsar
        if request.sid != criador_sid:
            emit('erro', {'msg': 'Apenas o criador da sala pode expulsar jogadores'})
            return
            
        # Encontrar o SID do jogador alvo pelo nome
        alvo_sid = None
        for sid, nome in salas[sala]['players'].items():
            if nome.lower() == nome_alvo.lower():
                alvo_sid = sid
                break
                
        if not alvo_sid:
            emit('erro', {'msg': 'Jogador não encontrado'})
            return
            
        # Remover jogador da partida
        partida = salas[sala]['partida']
        partida.jogadores = [j for j in partida.jogadores if j.nome.lower() != nome_alvo.lower()]
        
        # Remover do dicionário de players
        if alvo_sid in salas[sala]['players']:
            del salas[sala]['players'][alvo_sid]
        
        # Notificar o alvo
        emit('foi_expulso', {}, room=alvo_sid)
        
        # Notificar os outros jogadores
        emit('jogador_saiu', {
            'jogador': nome_alvo,
            'msg': f'{nome_alvo} foi expulso da sala',
            'jogadores_restantes': [j.nome for j in partida.jogadores]
        }, room=sala)
        
        # Reconfigurar alvos se necessário
        if len(partida.jogadores) >= 2:
            partida._configurar_alvos()
            
        # Remover da sala e desconectar
        leave_room(sala, sid=alvo_sid)
        socketio.server.disconnect(alvo_sid)
        
        logger.info(f'Jogador {nome_alvo} expulso da sala {sala} pelo criador')
        
    except Exception as e:
        logger.error(f'Erro ao expulsar jogador: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('enviar_palavras')
def receber_palavras(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()
        palavras = data.get('palavras', [])

        if not sala or sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return

        if not nome:
            emit('erro', {'msg': 'Nome é obrigatório'})
            return

        if not palavras:
            emit('erro', {'msg': 'Nenhuma palavra informada'})
            return

        partida = salas[sala]['partida']
        
        # Atualizar timestamp de último acesso
        salas[sala]['ultimo_acesso'] = time.time()

        # Buscar o jogador
        jogador = next((j for j in partida.jogadores if j.nome.lower() == nome.lower()), None)

        if not jogador:
            emit('erro', {'msg': 'Jogador não encontrado na sala'})
            return

        # Definir palavras
        jogador.definir_palavras(palavras)
        
        # Armazenar palavras também no SID para reconexão
        if 'palavras' not in salas[sala]:
            salas[sala]['palavras'] = {}
        salas[sala]['palavras'][request.sid] = palavras

        # Informar que as palavras foram recebidas
        emit('palavras_recebidas', {
            'msg': 'Suas palavras foram recebidas! Aguardando os outros jogadores...'
        })

        # Informar o status das palavras para todos na sala
        status_jogadores = []
        for j in partida.jogadores:
            status_jogadores.append({
                'nome': j.nome,
                'palavras_definidas': len(j.palavras) == partida.config.num_palavras
            })

        emit('status_palavras_atualizado', {
            'msg': f'{nome} definiu suas palavras!',
            'status_jogadores': status_jogadores
        }, room=sala)

        # Verificar se todos definiram as palavras e iniciar o jogo
        verificar_iniciar_jogo(sala)

    except Exception as e:
        logger.error(f'Erro ao receber palavras: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('tentar_adivinhar')
def tentar_adivinhar(data):
    try:
        sala = data.get('sala', '')
        nome = data.get('nome', '')
        palavra = data.get('palavra', '').strip()

        if not sala or sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return

        partida = salas[sala]['partida']
        
        # Atualizar timestamp de último acesso
        salas[sala]['ultimo_acesso'] = time.time()

        # Verificar se é a vez do jogador
        if partida.get_jogador_da_vez() != nome:
            emit('erro', {'msg': 'Não é sua vez de jogar'})
            return

        # Tentar adivinhar
        resultado = partida.tentar_adivinhar(nome, palavra)
        
        # Obter estado atualizado
        estado = partida.get_estado_jogo()

        # Emitir resultado
        emit('resposta_tentativa', {
            'jogador': nome,
            'palavra_tentada': palavra,
            'acertou': resultado['acertou'],
            'mensagem': resultado['mensagem'],
            'estado': estado
        }, room=sala)

        # Verificar se alguém ganhou
        if estado.get('vencedor'):
            emit('fim_de_jogo', {
                'mensagem': f'🎉 {estado["vencedor"]} venceu o jogo!',
                'estado': estado
            }, room=sala)

    except Exception as e:
        logger.error(f'Erro ao tentar adivinhar: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('enviar_mensagem_chat')
def enviar_mensagem_chat(data):
    try:
        sala = data.get('sala', '')
        nome = data.get('nome', '')
        mensagem = data.get('mensagem', '').strip()

        if not sala or sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return

        if not nome or not mensagem:
            return

        # Limitar tamanho da mensagem
        mensagem = mensagem[:200]
        
        # Atualizar timestamp de último acesso
        salas[sala]['ultimo_acesso'] = time.time()

        partida = salas[sala]['partida']
        partida.adicionar_mensagem_chat(nome, mensagem)

        # Timestamp no formato HH:MM:SS
        import datetime
        timestamp = datetime.datetime.now().strftime('%H:%M:%S')

        emit('nova_mensagem_chat', {
            'jogador': nome,
            'mensagem': mensagem,
            'timestamp': timestamp
        }, room=sala)

    except Exception as e:
        logger.error(f'Erro ao enviar mensagem: {str(e)}')

@socketio.on('enviar_emoji')
def enviar_emoji(data):
    try:
        sala = data.get('sala', '')
        nome = data.get('nome', '')
        emoji = data.get('emoji', '')

        if not sala or sala not in salas:
            return

        if not nome or not emoji:
            return

        # Atualizar timestamp de último acesso
        salas[sala]['ultimo_acesso'] = time.time()

        # Enviar emoji para todos na sala
        emit('emoji_recebido', {
            'nome': nome,
            'emoji': emoji
        }, room=sala)

    except Exception as e:
        logger.error(f'Erro ao enviar emoji: {str(e)}')

@socketio.on('obter_gabarito')
def obter_gabarito(data):
    try:
        sala = data.get('sala', '')

        if not sala or sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return

        partida = salas[sala]['partida']
        gabarito = partida.get_gabarito_completo()

        emit('gabarito_completo', {
            'gabarito': gabarito
        }, room=sala)

    except Exception as e:
        logger.error(f'Erro ao obter gabarito: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('novo_jogo')
def novo_jogo(data):
    try:
        sala = data.get('sala', '')
        nome = data.get('nome', '')

        if not sala or sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return

        # Apenas o criador pode reiniciar
        if request.sid != salas[sala]['criador']:
            emit('erro', {'msg': 'Apenas o criador da sala pode iniciar um novo jogo'})
            return
            
        partida = salas[sala]['partida']
        partida.reiniciar_jogo()

        # Limpar palavras armazenadas
        if 'palavras' in salas[sala]:
            salas[sala]['palavras'] = {}

        emit('jogo_reiniciado', {
            'msg': 'Jogo reiniciado! Todos devem definir novas palavras.'
        }, room=sala)

    except Exception as e:
        logger.error(f'Erro ao reiniciar jogo: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
