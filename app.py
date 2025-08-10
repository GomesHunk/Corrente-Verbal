import os
import time
import random
import string
import logging
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from jogo import Jogador, PartidaMultiplayer, Configuracao
from health import register_health_routes

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'jogo_das_palavras_secret')

# Detectar se está em produção (Render)
IS_PRODUCTION = os.environ.get('RENDER') is not None

# Configurações condicionais para SocketIO
if IS_PRODUCTION:
    # Usa gevent no Render (compatível com gunicorn worker gevent)
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        ping_timeout=60,
        ping_interval=25,
        logger=False,
        engineio_logger=False,
        async_mode='gevent'
    )
else:
    socketio = SocketIO(
        app,
        cors_allowed_origins="*",
        ping_timeout=120,
        ping_interval=60,
        logger=True,
        engineio_logger=True,
        async_mode='threading'
    )

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Registrar rotas de health check
register_health_routes(app)

salas = {}

# Pool de possíveis "memes" locais (arquivos em static/avatars/<slug>.(svg|webp|png|jpg|jpeg))
AVATAR_MEME_SLUGS = [
    "dollynho",
    "gravida-de-taubate",
    "galo-cego",
    "supla",
    "gretchen",
    "yudi",
    "cachorro-caramelo",
    "meme-troll",
    "chaves",
    "tiozao-do-pave",
]


def _dicebear_avatar(seed: str, style: str = "adventurer-neutral", size: int = 80) -> str:
    s = "".join(ch for ch in str(seed) if ch.isalnum()) or "seed"
    return f"https://api.dicebear.com/7.x/{style}/svg?seed={s}&radius=50&backgroundType=gradientLinear&size={size}"


def _local_avatar_url(slug: str) -> str | None:
    static_dir = app.static_folder or "static"
    base = os.path.join(static_dir, "avatars")
    for ext in (".svg", ".webp", ".png", ".jpg", ".jpeg"):
        candidate = os.path.join(base, f"{slug}{ext}")
        if os.path.exists(candidate):
            return f"/static/avatars/{slug}{ext}"
    return None


def _pick_avatar_url_by_seed(seed: str) -> str:
    try:
        idx = abs(hash(seed)) % len(AVATAR_MEME_SLUGS)
        slug = AVATAR_MEME_SLUGS[idx]
        local_url = _local_avatar_url(slug)
        if local_url:
            return local_url
    except Exception:
        pass
    return _dicebear_avatar(seed)


def _get_avatar_for(sala: dict, nome: str) -> str:
    # Usa player_id se disponível para manter estabilidade; fallback para nome
    players_ids = sala.get('player_ids', {})
    seed = players_ids.get(nome.lower()) or nome
    sala.setdefault('avatars', {})
    if nome not in sala['avatars']:
        sala['avatars'][nome] = _pick_avatar_url_by_seed(seed)
    return sala['avatars'][nome]


# ===== Helpers de sala =====
def nomes_conectados(sala):
    """Lista de nomes online (derivados de players SID->nome atuais)."""
    try:
        return list(sala.get('players', {}).values())
    except Exception:
        return []


def broadcast_status_prontos(codigo):
    """Emite o status de prontos considerando apenas jogadores online e excluindo o criador."""
    try:
        if codigo not in salas:
            return
        sala = salas[codigo]
        partida = sala['partida']
        criador_sid = sala.get('criador')
        nome_criador = sala.get('players', {}).get(criador_sid)
        nomes_online = set(nomes_conectados(sala))
        players_prontos = sala.get('players_prontos', set())

        jogadores_info = []
        for j in partida.jogadores:
            if j.nome in nomes_online:
                jogadores_info.append({
                    'nome': j.nome,
                    'pronto': j.nome in players_prontos,
                    'criador': j.nome == nome_criador,
                    'avatar': _get_avatar_for(sala, j.nome)
                })

        nao_criadores_online = {n for n in nomes_online if n != nome_criador}
        prontos_sem_host = sum(1 for n in nao_criadores_online if n in players_prontos)
        todos_prontos = (len(nao_criadores_online) > 0 and prontos_sem_host == len(nao_criadores_online))

        emit('status_prontos_atualizado', {
            'jogadores': jogadores_info,
            'todos_prontos': todos_prontos,
            'total_jogadores': len(nomes_online),
            'jogadores_prontos': prontos_sem_host
        }, room=codigo)
    except Exception as e:
        logger.error(f'Erro ao emitir status de prontos: {e}', exc_info=True)

def limpar_salas_inativas():
    """Remove salas inativas (sem jogadores há mais de 1 hora) ou marcadas para remoção (após 5 minutos)"""
    tempo_atual = time.time()
    
    salas_para_remover = []
    for codigo, sala in salas.items():
        # Remover salas inativas há mais de 1 hora
        if 'ultimo_acesso' in sala and (tempo_atual - sala['ultimo_acesso']) > 3600:
            # Remover apenas se não houver jogadores
            if len(sala['players']) == 0:
                salas_para_remover.append(codigo)
                logger.info(f'Sala inativa {codigo} será removida (inativa por mais de 1 hora)')
        
        # Remover salas marcadas para remoção após o tempo definido
        if 'marcada_para_remocao' in sala and tempo_atual > sala['marcada_para_remocao']:
            # Se ainda houver jogadores, estender o prazo
            if len(sala['players']) > 0:
                logger.info(f'Estendendo prazo de remoção da sala {codigo} - ainda tem {len(sala["players"])} jogadores')
                sala['marcada_para_remocao'] = tempo_atual + 300  # mais 5 minutos
            else:
                # Verificar se a sala foi criada recentemente (menos de 1 minuto)
                sala_recente = False
                if 'criada_em' in sala and (tempo_atual - sala['criada_em']) < 60:
                    # Sala recém-criada - dar mais tempo para o criador reconectar
                    sala_recente = True
                    logger.info(f'Sala {codigo} é recente, adiando remoção')
                    sala['marcada_para_remocao'] = tempo_atual + 120  # mais 2 minutos
                
                if not sala_recente:
                    salas_para_remover.append(codigo)
                    logger.info(f'Sala {codigo} será removida (marcada para remoção e tempo expirado)')
    
    # Remover as salas identificadas
    for codigo in salas_para_remover:
        if codigo in salas:  # Verificação extra para evitar KeyError
            del salas[codigo]
            logger.info(f'Sala {codigo} removida')

def verificar_iniciar_jogo(codigo):
    """Verifica se o jogo pode ser iniciado e o inicia se possível"""
    if codigo not in salas:
        logger.warning(f'Tentativa de verificar iniciar jogo em sala inexistente: {codigo}')
        return False
    
    sala = salas[codigo]
    partida = sala['partida']
    
    # Verificar se temos pelo menos 2 jogadores EFETIVAMENTE NA PARTIDA
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
        
        # Notificar todos sobre quem ainda não definiu palavras
        emit('status_palavras_atualizado', {
            'msg': 'Aguardando palavras de alguns jogadores',
            'jogadores_pendentes': jogadores_sem_palavras
        }, room=codigo)
        return False
    
    # Tudo pronto, iniciar jogo!
    try:
        partida.iniciar_jogo()
        
        estado = partida.get_estado_jogo()
        # Incluir info do criador no estado
        estado['criador'] = sala.get('criador')
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

def limpar_jogadores_desconectados():
    """Remove jogadores desconectados após período de reconexão"""
    tempo_atual = time.time()
    
    for codigo, sala in list(salas.items()):
        if 'desconexoes' in sala:
            jogadores_para_remover = []
            
            for nome_jogador, tempo_desconexao in list(sala['desconexoes'].items()):
                if tempo_atual - tempo_desconexao > 30:  # 30 segundos para reconectar
                    jogadores_para_remover.append(nome_jogador)
            
            # Remover jogadores que não reconectaram no tempo
            for nome_jogador in jogadores_para_remover:
                partida = sala['partida']
                partida.jogadores = [j for j in partida.jogadores if j.nome.lower() != nome_jogador.lower()]
                
                # Remover da lista de desconexões
                del sala['desconexoes'][nome_jogador]
                
                # Notificar os outros na sala
                emit('jogador_saiu', {
                    'jogador': nome_jogador,
                    'msg': f'{nome_jogador} saiu da sala (tempo de reconexão expirou)',
                    'jogadores_restantes': [j.nome for j in partida.jogadores]
                }, room=codigo)
                
                logger.info(f'Jogador {nome_jogador} removido da sala {codigo} (tempo de reconexão expirou)')
                
                # Se criador atual não tem SID válido, promover alguém conectado
                criador_sid = sala.get('criador')
                if criador_sid not in sala.get('players', {}) and len(sala.get('players', {})) > 0:
                    novo_criador_sid, novo_criador_nome = next(iter(sala['players'].items()))
                    sala['criador'] = novo_criador_sid
                    emit('novo_criador', { 'nome': novo_criador_nome }, room=codigo)
                
                # Reconfigurar alvos se necessário e o jogo já tiver iniciado
                if len(partida.jogadores) >= 2:
                    try:
                        estado = partida.get_estado_jogo()
                        if estado and 'jogador_da_vez' in estado:
                            partida._configurar_alvos()
                            estado = partida.get_estado_jogo()
                            estado['criador'] = sala.get('criador')
                            emit('estado_atualizado', {'estado': estado}, room=codigo)
                    except Exception:
                        pass

def limpar_mensagens_antigas():
    """Limita o número de mensagens de chat por sala para economizar memória"""
    for codigo, sala in salas.items():
        if 'partida' in sala:
            partida = sala['partida']
            if hasattr(partida, 'mensagens_chat') and len(partida.mensagens_chat) > 50:
                partida.mensagens_chat = partida.mensagens_chat[-50:]  # Manter apenas as 50 mais recentes

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/debug')
def debug_page():
    from flask import send_from_directory
    return send_from_directory('.', 'debug_page.html')

@app.route('/teste-meusid')
def teste_meusid():
    from flask import send_from_directory
    return send_from_directory('.', 'teste_meusid.html')

@app.route('/sala/<codigo>')
def sala_jogo(codigo):
    return render_template('jogo.html')

@socketio.on('connect')
def on_connect():
    logger.info(f'Cliente conectado: {request.sid}')
    # Limpar recursos para economizar memória
    limpar_salas_inativas()
    limpar_jogadores_desconectados()
    limpar_mensagens_antigas()
    
    # Debug - mostrar salas ativas após cada conexão
    debug_salas()

@socketio.on('disconnect')
def on_disconnect():
    logger.info(f'Cliente desconectado: {request.sid}')
    
    # Procurar o jogador em todas as salas
    for codigo, sala in list(salas.items()):
        if request.sid in sala['players']:
            nome_jogador = sala['players'][request.sid]
            
            # Remover da lista de players deste SID
            del sala['players'][request.sid]

            # Remover do set de prontos imediatamente para não travar o início
            try:
                sala.setdefault('players_prontos', set()).discard(nome_jogador)
            except Exception:
                pass

            # Atualizar status de prontos
            broadcast_status_prontos(codigo)
            
            # Se for o criador, promover automaticamente outro jogador se houver
            if request.sid == sala['criador']:
                tempo_atual = time.time()
                if len(sala['players']) > 0:
                    # Promover o primeiro SID disponível
                    novo_criador_sid, novo_criador_nome = next(iter(sala['players'].items()))
                    sala['criador'] = novo_criador_sid
                    emit('novo_criador', { 'nome': novo_criador_nome }, room=codigo)
                    logger.info(f'Criador desconectou na sala {codigo}. Novo criador: {novo_criador_nome}')
                else:
                    # Sem jogadores restantes: marcar para remoção rápida
                    sala['marcada_para_remocao'] = tempo_atual + 60
                    logger.info(f'Sala {codigo} marcada para remoção (criador saiu e não há mais jogadores)')
                # Atualizar o último acesso
                sala['ultimo_acesso'] = tempo_atual
                continue
            # Verificar se o jogador ainda tem conexões ativas (em outras abas)
            jogador_ainda_conectado = False
            for sid, nome in sala['players'].items():
                if nome.lower() == nome_jogador.lower():
                    jogador_ainda_conectado = True
                    break
                    
            # Se o jogador não estiver mais conectado, remover da partida após 30 segundos (permitir reconexão)
            if not jogador_ainda_conectado:
                # Definir timestamp de desconexão para permitir janela de reconexão
                sala['desconexoes'] = sala.get('desconexoes', {})
                sala['desconexoes'][nome_jogador] = time.time()
                
                # Notificar os outros na sala
                emit('jogador_desconectado', {
                    'jogador': nome_jogador,
                    'msg': f'{nome_jogador} desconectou-se (tem 30 segundos para reconectar)',
                    'jogadores_restantes': [j.nome for j in sala['partida'].jogadores]
                }, room=codigo)
                
                logger.info(f'Jogador {nome_jogador} desconectado da sala {codigo} (janela de reconexão iniciada)')

@socketio.on('criar_sala')
def criar_sala(data):
    try:
        logger.info(f'=== INÍCIO CRIAR_SALA ===')
        logger.info(f'Data recebida: {data}')
        logger.info(f'Request SID: {request.sid}')
        
        nome = data.get('nome', '').strip()
        num_palavras = int(data.get('num_palavras', 5))
        # Tornar max_jogadores opcional - usar 10 como padrão (máximo)
        max_jogadores = int(data.get('max_jogadores', 10)) 
        modo = (data.get('modo') or 'classico').strip().lower()
        if modo not in ('classico', 'cooperativo', 'duelo', 'relampago'):
            modo = 'classico'
        # Novo: capturar player_id (para identidade estável/avatares)
        player_id = (data or {}).get('player_id')

        logger.info(f'Parâmetros processados: nome={nome}, palavras={num_palavras}, max={max_jogadores}, modo={modo}')

        # Validações básicas
        if not nome:
            logger.warning('Nome vazio - rejeitando criação')
            emit('erro', {'msg': 'Nome é obrigatório'})
            return
        if len(nome) > 20:
            logger.warning(f'Nome muito longo ({len(nome)} chars) - rejeitando')
            emit('erro', {'msg': 'Nome deve ter no máximo 20 caracteres'})
            return

        # Gera código único com mais tentativas
        codigo = None
        for tentativa in range(20):  # Aumentado de 10 para 20
            codigo_tentativa = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
            if codigo_tentativa not in salas:
                codigo = codigo_tentativa
                logger.info(f'Código gerado na tentativa {tentativa + 1}: {codigo}')
                break
                
        # Se não conseguir gerar um código único, gerar um mais longo
        if not codigo:
            codigo = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            logger.warning(f'Usando código longo devido a colisões: {codigo}')
            
        logger.info(f'Criando sala com código: {codigo} por {nome} ({request.sid})')

        # Cria configuração e partida
        config = Configuracao(num_palavras, max_jogadores)
        partida = PartidaMultiplayer(config)
        partida.codigo_sala = codigo

        # Cria jogador e adiciona à partida
        jogador = Jogador(nome, config.num_palavras)
        partida.adicionar_jogador(jogador)

        # Salva o estado da sala
        tempo_atual = time.time()
        salas[codigo] = {
            'partida': partida,
            'criador': request.sid,
            'players': { request.sid: nome },
            'players_prontos': set(),
            'palavras': {},
            'player_ids': { nome.lower(): player_id } if player_id else {},
            'avatars': {},
            'ultimo_acesso': tempo_atual,
            'criada_em': tempo_atual,
            'modo': modo,
        }
        # Definir avatar do criador
        _get_avatar_for(salas[codigo], nome)

        logger.info(f'Sala {codigo} salva no dicionário. Total de salas: {len(salas)}')

        # Entra na sala (Socket.IO room)
        join_room(codigo)
        logger.info(f'Jogador {nome} entrou na room {codigo}')

        # Preparar resposta
        resposta = {
            'codigo': codigo,
            'nome': nome,
            'config': {
                'num_palavras': num_palavras,
                'max_jogadores': max_jogadores
            },
            'players': salas[codigo]['players'],
            'criador': salas[codigo]['criador'],
            'modo': modo
        }

        logger.info(f'Enviando resposta sala_criada: {resposta}')

        # Emite confirmação de criação, incluindo players e criador
        emit('sala_criada', resposta)
        
        # Logar detalhes da sala criada para debug
        debug_salas()

        logger.info(f'=== SUCESSO CRIAR_SALA: {codigo} ===')

    except Exception as e:
        logger.error(f'=== ERRO CRIAR_SALA ===')
        logger.error(f'Erro: {str(e)}')
        logger.error(f'Tipo: {type(e)}')
        import traceback
        logger.error(f'Traceback: {traceback.format_exc()}')
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('entrar_na_sala')
def entrar_na_sala(data):
    try:
        # Garantir que o código de sala seja sempre normalizado
        codigo_original = data.get('sala', '')
        codigo = codigo_original.strip().upper()
        nome = data.get('nome', '').strip()
        player_id = (data or {}).get('player_id')
        
        logger.info(f'Tentativa de entrar na sala: "{codigo}" por jogador "{nome}" (SID: {request.sid})')

        # Verificar se a sala existe
        if not codigo:
            logger.warning(f'Tentativa de entrar em sala com código vazio: {request.sid}')
            emit('erro', {'msg': 'Código da sala é obrigatório'})
            return
        if codigo not in salas:
            logger.warning(f'Sala não encontrada: "{codigo}" (original: "{codigo_original}"). Salas disponíveis: {list(salas.keys())}')
            emit('erro', {'msg': 'Sala não encontrada. Verifique o código e tente novamente.'})
            return
        if not nome:
            logger.warning(f'Tentativa de entrar na sala {codigo} sem nome: {request.sid}')
            emit('erro', {'msg': 'Nome é obrigatório'})
            return

        sala = salas[codigo]
        partida = sala['partida']
        sala['ultimo_acesso'] = time.time()

        # Armazenar/validar player_id para o nome
        sala.setdefault('player_ids', {})
        sala.setdefault('avatars', {})
        nome_key = nome.lower()
        if player_id:
            existente_pid = sala['player_ids'].get(nome_key)
            if existente_pid and existente_pid != player_id:
                emit('erro', {'msg': 'Este nome já está em uso na sala. Escolha outro.'})
                return
            sala['player_ids'][nome_key] = player_id

        # Verifica se o jogador já está na sala (pelo nome)
        jogador_existente = next((j for j in partida.jogadores if j.nome.lower() == nome_key), None)

        # Verificar criador atual por SID → nome
        criador_sid_atual = sala.get('criador')
        nome_criador = None
        for sid, nome_player in sala.get('players', {}).items():
            if sid == criador_sid_atual:
                nome_criador = nome_player
                break

        eh_criador_desta_conexao = (request.sid == criador_sid_atual)

        if not jogador_existente:
            # Novo jogador
            if len(partida.jogadores) >= partida.config.max_jogadores:
                emit('erro', {'msg': 'A sala está cheia.'})
                return
            if len(partida.jogadores) == 0:
                sala['criador'] = request.sid
                eh_criador_desta_conexao = True
            jogador = Jogador(nome, partida.config.num_palavras)
            partida.adicionar_jogador(jogador)
            logger.info(f'Jogador {nome} ({request.sid}) entrou na sala {codigo}')
        else:
            # Re-conexão: mover mapping de SID antigo para o novo, se existir
            sids_mesmo_nome = [sid for sid, n in sala['players'].items() if n.lower() == nome_key and sid != request.sid]
            for old_sid in sids_mesmo_nome:
                # Migrar palavras do old_sid para o novo SID
                if 'palavras' in sala and old_sid in sala['palavras']:
                    sala['palavras'][request.sid] = sala['palavras'].get(old_sid, [])
                    try:
                        del sala['palavras'][old_sid]
                    except KeyError:
                        pass
                try:
                    del sala['players'][old_sid]
                except KeyError:
                    pass
            # Se reconectou e era o criador (por nome), atualizar criador para o novo SID
            if nome_criador and nome.lower() == nome_criador.lower():
                sala['criador'] = request.sid
                eh_criador_desta_conexao = True
            logger.info(f'Jogador {nome} ({request.sid}) reconectou na sala {codigo}')

        # Entrar na room e registrar este SID → nome
        join_room(codigo)
        sala['players'][request.sid] = nome
        # Garantir avatar do jogador
        _get_avatar_for(sala, nome)

        # Limpar marca de desconexão se houver
        if 'desconexoes' in sala and nome in sala['desconexoes']:
            try:
                del sala['desconexoes'][nome]
            except KeyError:
                pass
            emit('aviso', {'msg': f'{nome} reconectou.'}, room=codigo)

        # Preparar informações dos jogadores com status de pronto (APENAS online)
        jogadores_info = []
        players_prontos = sala.get('players_prontos', set())
        criador_sid_atual = sala.get('criador')
        nome_criador_atual = None
        for sid, nome_player in sala.get('players', {}).items():
            if sid == criador_sid_atual:
                nome_criador_atual = nome_player
                break
        nomes_online = set(nomes_conectados(sala))
        for j in partida.jogadores:
            if j.nome in nomes_online:
                jogadores_info.append({
                    'nome': j.nome,
                    'pronto': j.nome in players_prontos,
                    'criador': j.nome == nome_criador_atual,
                    'avatar': _get_avatar_for(sala, j.nome)
                })

        # Broadcast do estado atual
        emit('jogador_entrou', {
            'jogador': nome,
            'jogadores': [j.nome for j in partida.jogadores],
            'total': len(nomes_online),
            'max': partida.config.max_jogadores,
            'jogadores_info': jogadores_info,
            'todos_prontos': verificar_todos_prontos(codigo),
            'modo': sala.get('modo', 'classico')
        }, room=codigo)

        # Enviar evento específico para o jogador que acabou de entrar informando se ele é o criador
        emit('meu_status', {
            'sou_criador': eh_criador_desta_conexao or (request.sid == sala.get('criador')),
            'nome': nome,
            'sala': codigo,
            'avatar': sala['avatars'].get(nome)
        })

        # Se o jogador já tinha enviado palavras, avisar
        if 'palavras' in sala:
            palavras_jogador = None
            for sid, player_nome in sala['players'].items():
                if player_nome.lower() == nome.lower() and sid in sala['palavras']:
                    palavras_jogador = sala['palavras'][sid]
                    break
            if palavras_jogador:
                emit('palavras_recebidas', {
                    'msg': 'Suas palavras foram recuperadas! Aguardando os outros jogadores...'
                })
                verificar_iniciar_jogo(codigo)

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
        
        # Remover do set de prontos
        salas[sala].setdefault('players_prontos', set()).discard(nome_alvo)
        
        # Atualizar status de prontos
        broadcast_status_prontos(sala)
        
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
        jogador_da_vez = partida.get_jogador_da_vez()
        if not jogador_da_vez or jogador_da_vez.nome != nome:
            emit('erro', {'msg': 'Não é sua vez de jogar'})
            return

        # Tentar adivinhar
        acertou, mensagem = partida.tentar_adivinhar(nome, palavra)
        
        # Obter estado atualizado
        estado = partida.get_estado_jogo()
        estado['criador'] = salas[sala].get('criador')

        # Emitir resultado para todos na sala
        emit('resposta_tentativa', {
            'jogador': nome,
            'palavra_tentada': palavra,
            'acertou': acertou,
            'mensagem': mensagem,
            'estado': estado
        }, room=sala)

        # Log para debug
        novo_jogador_da_vez = partida.get_jogador_da_vez()
        if novo_jogador_da_vez:
            logger.info(f'Sala {sala}: {nome} {"acertou" if acertou else "errou"} "{palavra}". Próximo: {novo_jogador_da_vez.nome}')
        
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

@socketio.on('iniciar_partida_manual')
def iniciar_partida_manual(data):
    """Permite ao criador iniciar a partida manualmente"""
    try:
        codigo = data.get('sala', '').upper()
        nome_criador = data.get('nome', '')
        
        logger.info(f'Tentativa de iniciar partida manual na sala {codigo} por {nome_criador}')
        
        if not codigo or not nome_criador:
            emit('error', {'msg': 'Dados inválidos para iniciar partida'})
            return
        
        if codigo not in salas:
            emit('error', {'msg': 'Sala não encontrada'})
            return
        
        sala = salas[codigo]
        partida = sala['partida']
        criador_sid = sala.get('criador')
        
        # Verificar se há jogadores suficientes
        if len(partida.jogadores) < 2:
            emit('error', {'msg': 'Mínimo de 2 jogadores necessário'})
            return
        
        # Verificar se quem está iniciando é o criador (por SID)
        if request.sid != criador_sid:
            emit('error', {'msg': 'Apenas o criador pode iniciar a partida'})
            return
        
        # Verificar se todos estão prontos (apenas online, exceto criador)
        if not verificar_todos_prontos(codigo):
            nomes_online = set(nomes_conectados(sala))
            criador_sid = sala.get('criador')
            nome_criador = sala.get('players', {}).get(criador_sid)
            nao_criadores_online = [n for n in nomes_online if n != nome_criador]
            players_prontos = sala.get('players_prontos', set())
            jogadores_nao_prontos = [n for n in nao_criadores_online if n not in players_prontos]
            emit('error', {'msg': f'Nem todos estão prontos. Aguardando: {", ".join(jogadores_nao_prontos)}'})
            return
        
        logger.info(f'Partida iniciada manualmente na sala {codigo} por {nome_criador}')
        
        # Emitir evento pode_comecar para todos na sala
        emit('pode_comecar', {
            'msg': 'Partida iniciada pelo criador! Definam suas palavras para começar.',
            'codigo': codigo,
            'num_palavras': partida.config.num_palavras,
            'jogadores': [j.nome for j in partida.jogadores]
        }, room=codigo)
        
    except Exception as e:
        logger.error(f'Erro ao iniciar partida manual: {e}', exc_info=True)
        emit('error', {'msg': 'Erro interno do servidor'})

def verificar_todos_prontos(codigo):
    """Verifica se todos os jogadores ONLINE (exceto criador) estão prontos para iniciar"""
    if codigo not in salas:
        return False
    
    sala = salas[codigo]
    partida = sala['partida']
    players_prontos = sala.get('players_prontos', set())
    
    # Precisa ter pelo menos 2 na partida e pelo menos 2 online
    nomes_online = set(nomes_conectados(sala))
    if len(partida.jogadores) < 2 or len(nomes_online) < 2:
        return False
    
    # Identificar o criador da sala
    criador_sid = sala.get('criador')
    nome_criador = sala.get('players', {}).get(criador_sid)
    
    # Apenas não-criadores online contam
    nao_criadores_online = {n for n in nomes_online if n != nome_criador}
    if not nao_criadores_online:
        return False
    
    return all(n in players_prontos for n in nao_criadores_online)

@socketio.on('marcar_pronto')
def marcar_pronto(data):
    """Marca um jogador como pronto para iniciar a partida"""
    try:
        codigo = data.get('sala', '').upper()
        nome = data.get('nome', '')
        pronto = data.get('pronto', True)
        
        logger.info(f'Jogador {nome} marcando-se como {"pronto" if pronto else "não pronto"} na sala {codigo}')
        
        if not codigo or not nome:
            emit('error', {'msg': 'Dados inválidos'})
            return
        
        if codigo not in salas:
            emit('error', {'msg': 'Sala não encontrada'})
            return
        
        sala = salas[codigo]
        partida = sala['partida']
        criador_sid = sala.get('criador')
        
        # Criador não marca pronto
        if request.sid == criador_sid:
            return
        
        # Verificar se o jogador está na sala
        if not any(j.nome == nome for j in partida.jogadores):
            emit('error', {'msg': 'Jogador não encontrado na sala'})
            return
        
        # Atualizar status de pronto
        sala.setdefault('players_prontos', set())
        if pronto:
            sala['players_prontos'].add(nome)
        else:
            sala['players_prontos'].discard(nome)
        
        # Emite status atualizado para todos
        broadcast_status_prontos(codigo)
        
        logger.info(f'Status de prontos emitido para sala {codigo}')
        
    except Exception as e:
        logger.error(f'Erro ao marcar pronto: {e}', exc_info=True)
        emit('error', {'msg': 'Erro interno do servidor'})

@socketio.on('selecionar_modo')
def selecionar_modo(data):
    try:
        codigo = (data or {}).get('sala', '').strip().upper() or request.args.get('sala') or ''
        nome = (data or {}).get('nome', '')
        modo = (data or {}).get('modo', 'classico')
        if not codigo or codigo not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        sala = salas[codigo]
        # Apenas o criador pode alterar
        if request.sid != sala.get('criador'):
            emit('erro', {'msg': 'Apenas o criador pode alterar o modo'})
            return
        if modo not in ('classico', 'cooperativo', 'duelo', 'relampago'):
            emit('erro', {'msg': 'Modo inválido'})
            return
        sala['modo'] = modo
        emit('modo_atualizado', { 'modo': modo }, room=codigo)
        logger.info(f'Sala {codigo}: modo alterado para {modo} por {nome}')
    except Exception as e:
        logger.error(f'Erro ao selecionar modo: {e}', exc_info=True)
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('transferir_criador')
def transferir_criador(data):
    try:
        codigo = (data or {}).get('sala', '').strip().upper()
        nome_destino = (data or {}).get('para', '').strip()
        if not codigo or codigo not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        sala = salas[codigo]
        if request.sid != sala.get('criador'):
            emit('erro', {'msg': 'Apenas o criador pode transferir a liderança'})
            return
        # Encontrar SID do destino
        destino_sid = None
        for sid, n in sala.get('players', {}).items():
            if n.lower() == nome_destino.lower():
                destino_sid = sid
                break
        if not destino_sid:
            emit('erro', {'msg': 'Jogador de destino não encontrado ou desconectado'})
            return
        sala['criador'] = destino_sid
        emit('novo_criador', { 'nome': nome_destino }, room=codigo)
        # Reemitir status de prontos com flag de criador atualizada
        partida = sala['partida']
        jogadores_info = []
        nome_criador_atual = nome_destino
        for j in partida.jogadores:
            jogadores_info.append({
                'nome': j.nome,
                'pronto': j.nome in sala.get('players_prontos', set()),
                'criador': j.nome == nome_criador_atual
            })
        emit('status_prontos_atualizado', {
            'jogadores': jogadores_info,
            'todos_prontos': verificar_todos_prontos(codigo),
            'total_jogadores': len(partida.jogadores),
            'jogadores_prontos': len(sala.get('players_prontos', set()))
        }, room=codigo)
        logger.info(f'Sala {codigo}: criador transferido para {nome_destino}')
    except Exception as e:
        logger.error(f'Erro ao transferir criador: {e}', exc_info=True)
        emit('erro', {'msg': 'Erro interno do servidor'})

@socketio.on('sair_da_sala')
def sair_da_sala(data):
    """Permite a um jogador sair explicitamente da sala"""
    try:
        codigo = (data or {}).get('sala', '').strip().upper()
        nome = (data or {}).get('nome', '').strip()
        if not codigo or codigo not in salas:
            emit('erro', {'msg': 'Sala não encontrada'})
            return
        sala = salas[codigo]
        partida = sala['partida']

        # Remover do mapa de sockets
        if request.sid in sala['players']:
            del sala['players'][request.sid]

        # Remover do set de prontos
        try:
            sala.setdefault('players_prontos', set()).discard(nome)
        except Exception:
            pass

        # Atualizar status de prontos
        broadcast_status_prontos(codigo)

        # Remover jogador da partida pelo nome
        nomes_antes = [j.nome for j in partida.jogadores]
        partida.jogadores = [j for j in partida.jogadores if j.nome.lower() != nome.lower()]
        nomes_depois = [j.nome for j in partida.jogadores]

        # Se o criador saiu, remarcar a sala para remoção ou promover outro
        if request.sid == sala.get('criador'):
            if partida.jogadores:
                # Promover primeiro jogador restante (pelo nome)
                novo_nome = partida.jogadores[0].nome
                for sid, n in sala.get('players', {}).items():
                    if n.lower() == novo_nome.lower():
                        sala['criador'] = sid
                        emit('novo_criador', { 'nome': novo_nome }, room=codigo)
                        break
            else:
                sala['marcada_para_remocao'] = time.time() + 60

        leave_room(codigo)

        # Notificar demais
        emit('jogador_saiu', {
            'jogador': nome or 'Um jogador',
            'msg': f'{nome or "Um jogador"} saiu da sala',
            'jogadores_restantes': [j.nome for j in partida.jogadores]
        }, room=codigo)

        # Se jogo em andamento e >=2, reconfigurar alvos
        if len(partida.jogadores) >= 2:
            try:
                partida._configurar_alvos()
                estado = partida.get_estado_jogo()
                emit('estado_atualizado', {'estado': estado}, room=codigo)
            except Exception:
                pass

    except Exception as e:
        logger.error(f'Erro em sair_da_sala: {e}', exc_info=True)
        emit('erro', {'msg': 'Erro interno do servidor'})

def debug_salas():
    """Função auxiliar para debug do estado das salas"""
    logger.info(f"Salas ativas: {len(salas)}")
    for codigo, sala in salas.items():
        logger.info(f"Sala {codigo}: {len(sala['partida'].jogadores)} jogadores, {len(sala['players'])} sockets, criador: {sala['criador']}")
    return len(salas)

def garantir_criador_na_sala(codigo):
    """Garante que sempre há um criador definido na sala"""
    if codigo not in salas:
        return False
    
    sala = salas[codigo]
    partida = sala['partida']
    
    # Se não há criador definido e há jogadores
    if not sala.get('criador') and len(partida.jogadores) > 0:
        # Fazer o primeiro jogador ser o criador
        primeiro_jogador = partida.jogadores[0]
        
        # Encontrar o SID deste jogador
        for sid, nome in sala.get('players', {}).items():
            if nome.lower() == primeiro_jogador.nome.lower():
                sala['criador'] = sid
                logger.info(f'Jogador {primeiro_jogador.nome} promovido a criador da sala {codigo}')
                return True
    
    return sala.get('criador') is not None

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
