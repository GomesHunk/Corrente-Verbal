from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from jogo import Jogador, PartidaMultiplayer, Configuracao
from health import register_health_routes
import logging
import os

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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/sala/<codigo>')
def sala_jogo(codigo):
    return render_template('jogo.html')

@socketio.on('connect')
def on_connect():
    logger.info(f'Cliente conectado: {request.sid}')

@socketio.on('disconnect')
def on_disconnect():
    logger.info(f'Cliente desconectado: {request.sid}')

@socketio.on('criar_sala')
def criar_sala(data):
    try:
        nome = data.get('nome', '').strip()
        num_palavras = int(data.get('num_palavras', 5))
        max_jogadores = int(data.get('max_jogadores', 2))

        # Validações básicas
        if not nome:
            emit('erro', {'msg': 'Nome é obrigatório'})
            return
        if len(nome) > 20:
            emit('erro', {'msg': 'Nome deve ter no máximo 20 caracteres'})
            return

        # Gera código único de 6 dígitos
        import random, string
        codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        # Cria configuração e partida
        config = Configuracao(num_palavras, max_jogadores)
        partida = PartidaMultiplayer(config)
        partida.codigo_sala = codigo

        # Cria jogador e adiciona à partida
        jogador = Jogador(nome, num_palavras)
        partida.adicionar_jogador(jogador)

        # === Atualização: salva o estado da sala com SID do criador e mapa de players ===
        salas[codigo] = {
            'partida': partida,
            'criador': request.sid,       # SID do socket que criou
            'players': {                  # map SID → nome
                request.sid: nome
            },
            'palavras': {}                # opcional, se usada
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

    except ValueError as e:
        logger.error(f'Erro ao entrar na sala {codigo}: {str(e)}')
        emit('erro', {'msg': str(e)})
    except Exception as e:
        logger.error(f'Erro ao entrar na sala: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})


@socketio.on('expulsar_jogador')
def expulsar_jogador(data):
    sala = data['sala']                # o código/nome da sala
    alvo_sid = data['sid']             # o socket ID do jogador a expulsar
    criador_sid = salas[sala]['criador']  # extraia do seu dicionário quem criou a sala

    # Só o criador pode mandar expulsar
    if request.sid != criador_sid:
        return

    # Notifica o alvo
    emit('foi_expulso', {}, room=alvo_sid)

    # Remove o alvo da sala e desconecta
    leave_room(sala, sid=alvo_sid)
    socketio.server.disconnect(alvo_sid)

@socketio.on('submit_palavras')
def submit_palavras(data):
    codigo = data['sala']
    lista_palavras = data['palavras']    # ex: ['casa','gato',…]
    # Armazena no dicionário, sem apagar o que já existe
    salas[codigo]['palavras'][request.sid] = lista_palavras

    # (Opcional) Notificar os demais de quem já enviou
    emit('palavras_atualizadas', {
        'sid': request.sid,
        'palavras': lista_palavras
    }, room=codigo)
    
@socketio.on('enviar_palavras')
def receber_palavras(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()
        palavras = data.get('palavras', [])
        
        if sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        
        partida = salas[sala]['partida']
        
        # Encontrar jogador
        jogador_encontrado = None
        for j in partida.jogadores:
            if j.nome == nome:
                jogador_encontrado = j
                break
        
        if not jogador_encontrado:
            emit('erro', {'msg': 'Jogador não encontrado na sala'})
            return
        
        # Definir palavras do jogador
        jogador_encontrado.definir_palavras(palavras)
        emit('palavras_recebidas', {'msg': 'Palavras definidas com sucesso!'})
        
        logger.info(f'Jogador {nome} definiu suas {len(palavras)} palavras na sala {sala}')
        
        # Criar status dos jogadores (quem já preencheu as palavras)
        status_jogadores = []
        for j in partida.jogadores:
            status_jogadores.append({
                'nome': j.nome,
                'palavras_definidas': len(j.palavras) == partida.config.num_palavras
            })
        
        # Notificar todos sobre o status atualizado
        emit('status_palavras_atualizado', {
            'jogador': nome,
            'msg': f'{nome} definiu suas palavras!',
            'status_jogadores': status_jogadores
        }, room=sala)
        
        # Verificar se todos os jogadores definiram suas palavras
        todos_prontos = all(len(j.palavras) == partida.config.num_palavras for j in partida.jogadores)
        
        if todos_prontos and len(partida.jogadores) >= 2:
            # Iniciar o jogo
            partida.iniciar_jogo()
            
            estado = partida.get_estado_jogo()
            emit('jogo_iniciado', {
                'msg': 'Todos definiram as palavras! O jogo começou!',
                'estado': estado
            }, room=sala)
            
            logger.info(f'Jogo iniciado na sala {sala} com {len(partida.jogadores)} jogadores')
            
    except ValueError as e:
        emit('erro', {'msg': str(e)})
    except Exception as e:
        logger.error(f'Erro ao receber palavras: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('tentar_adivinhar')
def tentativa(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()
        palavra_tentada = data.get('palavra', '').strip()
        
        if sala not in salas:
            emit('erro', {'msg': 'Partida não encontrada'})
            return
        
        partida = salas[sala]['partida']
        
        if not palavra_tentada:
            emit('erro', {'msg': 'Digite uma palavra para tentar'})
            return
        
        # Executar a tentativa
        acertou, resposta = partida.tentar_adivinhar(nome, palavra_tentada)
        
        # Obter estado atualizado do jogo
        estado = partida.get_estado_jogo()
        
        # Enviar resposta para todos na sala
        emit('resposta_tentativa', {
            'jogador': nome,
            'palavra_tentada': palavra_tentada,
            'acertou': acertou,
            'mensagem': resposta,
            'estado': estado
        }, room=sala)
        
        logger.info(f'Tentativa de {nome} na sala {sala}: {palavra_tentada} - {"Acertou" if acertou else "Errou"}')
        
        # Verificar se o jogo terminou
        if estado['vencedor']:
            emit('fim_de_jogo', {
                'vencedor': estado['vencedor'],
                'mensagem': f'{estado["vencedor"]} venceu o jogo!'
            }, room=sala)
            
            logger.info(f'Jogo terminou na sala {sala}. Vencedor: {estado["vencedor"]}')
            
    except Exception as e:
        logger.error(f'Erro na tentativa: {str(e)}')
        emit('erro', {'msg': str(e) if 'não é sua vez' in str(e).lower() else 'Erro interno do servidor'})

@socketio.on('obter_estado')
def obter_estado(data):
    try:
        sala = data.get('sala', '').strip().upper()
        
        if sala not in salas:
            emit('erro', {'msg': 'Partida não encontrada'})
            return
        
        partida = salas[sala]['partida']
        estado = partida.get_estado_jogo()
        emit('estado_atualizado', {'estado': estado})
        
    except Exception as e:
        logger.error(f'Erro ao obter estado: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('enviar_mensagem_chat')
def receber_mensagem_chat(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()
        mensagem = data.get('mensagem', '').strip()
        
        if not sala or not nome or not mensagem:
            emit('erro', {'msg': 'Dados incompletos para enviar mensagem'})
            return
        
        if sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        
        partida = salas[sala]['partida']
        
        # Verificar se o jogador está na sala
        jogador_encontrado = False
        for j in partida.jogadores:
            if j.nome == nome:
                jogador_encontrado = True
                break
        
        if not jogador_encontrado:
            emit('erro', {'msg': 'Jogador não encontrado na sala'})
            return
        
        # Adicionar mensagem ao chat da partida
        partida.adicionar_mensagem_chat(nome, mensagem)
        
        # Enviar mensagem para todos na sala
        emit('nova_mensagem_chat', {
            'jogador': nome,
            'mensagem': mensagem,
            'timestamp': partida.mensagens_chat[-1]['timestamp']
        }, room=sala)
        
        logger.info(f'Mensagem de {nome} na sala {sala}: {mensagem}')
        
    except Exception as e:
        logger.error(f'Erro ao enviar mensagem: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('novo_jogo')
def novo_jogo(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()
        
        if sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        
        partida = salas[sala]['partida']
        
        # Verificar se o jogador está na sala
        jogador_encontrado = False
        for j in partida.jogadores:
            if j.nome == nome:
                jogador_encontrado = True
                break
        
        if not jogador_encontrado:
            emit('erro', {'msg': 'Jogador não encontrado na sala'})
            return
        
        # Reiniciar o jogo
        partida.reiniciar_jogo()
        
        # Notificar todos na sala
        emit('jogo_reiniciado', {
            'msg': f'{nome} iniciou um novo jogo!',
            'jogadores': [j.nome for j in partida.jogadores],
            'config': {
                'num_palavras': partida.config.num_palavras,
                'max_jogadores': partida.config.max_jogadores
            }
        }, room=sala)
        
        logger.info(f'Novo jogo iniciado na sala {sala} por {nome}')
        
    except Exception as e:
        logger.error(f'Erro ao iniciar novo jogo: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('obter_gabarito')
def obter_gabarito(data):
    try:
        sala = data.get('sala', '').strip().upper()
        
        if sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        
        partida = salas[sala]['partida']
        gabarito = partida.get_gabarito_completo()
        
        if gabarito:
            emit('gabarito_completo', {'gabarito': gabarito})
        else:
            emit('erro', {'msg': 'Jogo ainda não terminou'})
        
    except Exception as e:
        logger.error(f'Erro ao obter gabarito: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('sair_da_sala')
def sair_da_sala(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()
        
        leave_room(sala)
        
        if sala in salas:
            partida = salas[sala]['partida']
            
            # Remover jogador da sala
            partida.jogadores = [j for j in partida.jogadores if j.nome != nome]
            
            if len(partida.jogadores) == 0:
                del salas[sala]
                logger.info(f'Sala {sala} removida')
            else:
                # Reconfigurar alvos se necessário
                if len(partida.jogadores) >= 2:
                    partida._configurar_alvos()
                
                emit('jogador_saiu', {
                    'jogador': nome,
                    'msg': f'{nome} saiu da sala',
                    'jogadores_restantes': [j.nome for j in partida.jogadores]
                }, room=sala)
        
        emit('saiu_da_sala', {'msg': 'Você saiu da sala'})
        
    except Exception as e:
        logger.error(f'Erro ao sair da sala: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('enviar_emoji')
def enviar_emoji(data):
    try:
        sala = data.get('sala', '').strip().upper()
        nome = data.get('nome', '').strip()
        emoji = data.get('emoji', '').strip()
        
        if not sala or not nome or not emoji:
            emit('erro', {'msg': 'Dados incompletos para enviar emoji'})
            return
        
        if sala not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        
        partida = salas[sala]['partida']
        
        # Verificar se o jogador está na sala
        jogador_encontrado = False
        for j in partida.jogadores:
            if j.nome == nome:
                jogador_encontrado = True
                break
        
        if not jogador_encontrado:
            emit('erro', {'msg': 'Jogador não encontrado na sala'})
            return
        
        # Lista de emojis permitidos (segurança)
        emojis_permitidos = ['👍', '👎', '🤔', '😂', '😱', '🔥', '💡', '❤️']
        if emoji not in emojis_permitidos:
            emit('erro', {'msg': 'Emoji não permitido'})
            return
        
        # Enviar emoji para todos na sala
        emit('emoji_recebido', {
            'nome': nome,
            'emoji': emoji
        }, room=sala)
        
        logger.info(f'Emoji {emoji} enviado por {nome} na sala {sala}')
    except Exception as e:
        logger.error(f'Erro ao enviar emoji: {str(e)}')
        emit('erro', {'msg': 'Erro interno do servidor'})

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, debug=False, host='0.0.0.0', port=port)
