from normalizador import NormalizadorTexto

class Configuracao:
    def __init__(self, num_palavras=5, max_jogadores=8):
        self.num_palavras = max(4, min(8, num_palavras))  # Entre 4 e 8
        self.max_jogadores = max(2, min(8, max_jogadores))  # Entre 2 e 8

class Jogador:
    def __init__(self, nome, num_palavras=5):
        self.nome = nome
        self.num_palavras = num_palavras
        self.palavras = []  # Lista com as N palavras definidas
        self.palavras_originais = []  # Lista com as palavras originais (antes da normalização)
        self.dicas = []     # Lista com a dica de cada palavra
        self.palavra_atual_index = 1  # Índice da palavra que está tentando adivinhar (começa na 2ª palavra)
        self.tentativas_erradas_atual = 0  # Erros na palavra atual
        self.tentativas_por_palavra = []  # Erros acumulados por palavra
        self.palavras_descobertas = []  # Controla quais palavras foram descobertas
        self.alvo_jogador = None  # Jogador cujas palavras este jogador deve adivinhar
        self.concluido = False  # Se terminou de adivinhar todas as palavras
        self.normalizador = NormalizadorTexto()  # Instância do normalizador
        self.avatar = '👤' # Avatar padrão do jogador

    def definir_palavras(self, lista_palavras):
        if len(lista_palavras) != self.num_palavras:
            raise ValueError(f"É necessário inserir exatamente {self.num_palavras} palavras.")
        
        # Validar palavras
        for palavra in lista_palavras:
            if not palavra or not palavra.strip():
                raise ValueError("Todas as palavras devem ser preenchidas.")
            if not palavra.replace(' ', '').isalpha():
                raise ValueError("As palavras devem conter apenas letras.")
            if len(palavra.strip()) < 2:
                raise ValueError("As palavras devem ter pelo menos 2 letras.")
        
        # Salvar palavras originais e normalizadas
        self.palavras_originais = [palavra.strip() for palavra in lista_palavras]
        self.palavras = []
        
        # Normalizar cada palavra
        for palavra_original in self.palavras_originais:
            palavra_normalizada = self.normalizador.normalizar(palavra_original)
            self.palavras.append(palavra_normalizada.lower())
        
        self.palavras_descobertas = [False] * self.num_palavras
        self.tentativas_por_palavra = [0] * self.num_palavras  # Inicializar tentativas por palavra
        
        # A primeira palavra já é considerada "descoberta" pois está completa
        self.palavras_descobertas[0] = True
        
        # Configurar dicas iniciais
        self.dicas = []
        for i, palavra in enumerate(self.palavras):
            if i == 0:
                # Primeira palavra: mostrar completa
                self.dicas.append(palavra)
            else:
                # Demais palavras: apenas primeira letra
                self.dicas.append(palavra[0])

    def get_dica_palavra_atual(self):
        """Retorna a dica da palavra que o jogador está tentando adivinhar atualmente"""
        if not self.alvo_jogador or self.palavra_atual_index >= len(self.alvo_jogador.palavras):
            return ""
        
        palavra = self.alvo_jogador.palavras[self.palavra_atual_index]
        
        if self.palavra_atual_index == 0:
            # Primeira palavra: sempre completa
            return palavra
        else:
            # Demais palavras: primeira letra + letras extras por erro
            letras_extras = self.tentativas_erradas_atual
            total_letras = min(len(palavra), 1 + letras_extras)
            return palavra[:total_letras]

    def atualizar_dicas_alvo(self):
        """Atualiza as dicas do alvo baseado nos erros acumulados"""
        if not self.alvo_jogador:
            return
        
        for i, palavra in enumerate(self.alvo_jogador.palavras):
            if i == 0:
                # Primeira palavra: sempre completa
                self.alvo_jogador.dicas[i] = palavra
            else:
                # Demais palavras: primeira letra + letras extras por erros
                if i < len(self.alvo_jogador.tentativas_por_palavra):
                    erros = self.alvo_jogador.tentativas_por_palavra[i]
                    total_letras = min(len(palavra), 1 + erros)
                    self.alvo_jogador.dicas[i] = palavra[:total_letras]

    def get_palavra_anterior(self):
        """Retorna a palavra anterior que foi descoberta (para referência)"""
        if not self.alvo_jogador or self.palavra_atual_index <= 0:
            return ""
        
        # Retorna a palavra anterior (índice atual - 1)
        return self.alvo_jogador.palavras[self.palavra_atual_index - 1]

    def tentar_adivinhar(self, palavra_tentada):
        """Tenta adivinhar a palavra atual do alvo"""
        if not self.alvo_jogador or self.concluido:
            return False, "Não há palavra para adivinhar"
        
        if self.palavra_atual_index >= len(self.alvo_jogador.palavras):
            return False, "Todas as palavras já foram descobertas"
        
        palavra_correta = self.alvo_jogador.palavras[self.palavra_atual_index]
        palavra_tentada_original = palavra_tentada.strip()
        
        # Normalizar a palavra tentada
        palavra_tentada_normalizada = self.normalizador.normalizar(palavra_tentada_original).lower()
        
        # Comparar usando o normalizador (considera variações de acentos)
        if self.normalizador.comparar_palavras(palavra_tentada_normalizada, palavra_correta):
            # Acertou!
            self.alvo_jogador.palavras_descobertas[self.palavra_atual_index] = True
            self.palavra_atual_index += 1
            self.tentativas_erradas_atual = 0
            
            # Atualizar dicas do alvo após acertar
            self.atualizar_dicas_alvo()
            
            # Verificar se houve correção automática
            mensagem_correcao = ""
            if self.normalizador.foi_corrigida(palavra_tentada_original, palavra_tentada_normalizada):
                mensagem_correcao = f" (corrigido de '{palavra_tentada_original}')"
            
            # Verificar se terminou todas as palavras
            if self.palavra_atual_index >= len(self.alvo_jogador.palavras):
                self.concluido = True
                return True, f"Parabéns! Você descobriu '{palavra_correta}'{mensagem_correcao} e completou todas as palavras!"
            
            return True, f"Correto! '{palavra_correta}'{mensagem_correcao} - Próxima palavra: {self.get_dica_palavra_atual()}"
        else:
            # Errou - incrementar tentativas da palavra atual no alvo
            self.tentativas_erradas_atual += 1
            if self.palavra_atual_index < len(self.alvo_jogador.tentativas_por_palavra):
                self.alvo_jogador.tentativas_por_palavra[self.palavra_atual_index] += 1
            
            # Atualizar dicas do alvo
            self.atualizar_dicas_alvo()
            
            nova_dica = self.get_dica_palavra_atual()
            
            # Verificar se há sugestão de correção
            sugestao = self.normalizador.sugerir_correcao(palavra_tentada_original)
            mensagem_sugestao = ""
            if sugestao and sugestao != palavra_tentada_normalizada:
                mensagem_sugestao = f" (você quis dizer '{sugestao}'?)"
            
            return False, f"Errou! Nova dica: {nova_dica}{mensagem_sugestao}"

    def descobrir_palavra(self, indice):
        """Marca uma palavra como descoberta"""
        if 0 <= indice < len(self.palavras_descobertas):
            self.palavras_descobertas[indice] = True
            
    def definir_avatar(self, avatar_url):
        """Define o avatar do jogador"""
        self.avatar = avatar_url


class PartidaMultiplayer:
    def __init__(self, configuracao):
        self.config = configuracao
        self.jogadores = []
        self.turno_atual = 0
        self.jogo_iniciado = False
        self.vencedor = None
        self.mensagens_chat = []
        self.codigo_sala = ""

    def adicionar_jogador(self, jogador):
        """Adiciona um jogador à partida"""
        if len(self.jogadores) >= self.config.max_jogadores:
            raise ValueError("Sala cheia")
        
        jogador.num_palavras = self.config.num_palavras
        self.jogadores.append(jogador)
        
        # Se atingiu o número mínimo, configurar alvos
        if len(self.jogadores) >= 2:
            self._configurar_alvos()

    def _configurar_alvos(self):
        """Configura a lógica circular de alvos"""
        for i, jogador in enumerate(self.jogadores):
            # Cada jogador tem como alvo o próximo na lista (circular)
            proximo_index = (i + 1) % len(self.jogadores)
            jogador.alvo_jogador = self.jogadores[proximo_index]

    def iniciar_jogo(self):
        """Inicia o jogo após todos jogadores definirem suas palavras"""
        if len(self.jogadores) < 2:
            raise ValueError("Necessário pelo menos 2 jogadores")
        
        # Verificar se todos definiram palavras
        for jogador in self.jogadores:
            if len(jogador.palavras) != self.config.num_palavras:
                raise ValueError(f"Jogador {jogador.nome} ainda não definiu suas palavras")
        
        self.jogo_iniciado = True
        self.turno_atual = 0

    def tentar_adivinhar(self, jogador_nome, palavra_tentada):
        """Processa uma tentativa de adivinhação"""
        if not self.jogo_iniciado:
            return False, "O jogo ainda não foi iniciado!"
        
        if self.vencedor:
            return False, "O jogo já terminou!"
        
        # Encontrar o jogador
        jogador_atual = None
        for j in self.jogadores:
            if j.nome == jogador_nome:
                jogador_atual = j
                break
        
        if not jogador_atual:
            return False, "Jogador não encontrado!"
        
        # Verificar se é a vez do jogador
        if self.jogadores[self.turno_atual] != jogador_atual:
            return False, "Não é sua vez!"
        
        # Tentar adivinhar
        acertou, mensagem = jogador_atual.tentar_adivinhar(palavra_tentada)
        
        # Verificar se alguém venceu
        if jogador_atual.concluido:
            self.vencedor = jogador_atual
        
        # Se errou, passa a vez para o próximo jogador
        if not acertou:
            self.turno_atual = (self.turno_atual + 1) % len(self.jogadores)
        
        return acertou, mensagem

    def get_jogador_da_vez(self):
        """Retorna o jogador da vez atual"""
        if self.jogadores and 0 <= self.turno_atual < len(self.jogadores):
            return self.jogadores[self.turno_atual]
        return None

    def adicionar_mensagem_chat(self, jogador_nome, mensagem):
        """Adiciona uma mensagem ao chat"""
        import datetime
        self.mensagens_chat.append({
            'jogador': jogador_nome,
            'mensagem': mensagem.strip(),
            'timestamp': datetime.datetime.now().strftime('%H:%M:%S')
        })
        
        # Manter apenas as últimas 50 mensagens
        if len(self.mensagens_chat) > 50:
            self.mensagens_chat = self.mensagens_chat[-50:]

    def get_estado_jogo(self):
        """Retorna o estado atual do jogo"""
        jogador_da_vez = self.get_jogador_da_vez()
        
        return {
            'turno_atual': self.turno_atual,
            'jogador_da_vez': jogador_da_vez.nome if jogador_da_vez else None,
            'jogo_iniciado': self.jogo_iniciado,
            'vencedor': self.vencedor.nome if self.vencedor else None,
            'config': {
                'num_palavras': self.config.num_palavras,
                'max_jogadores': self.config.max_jogadores
            },
            'jogadores': [
                {
                    'nome': j.nome,
                    'palavras_descobertas': j.palavras_descobertas,
                    'dicas': j.dicas,
                    'palavra_atual_index': j.palavra_atual_index,
                    'dica_atual': j.get_dica_palavra_atual(),
                    'palavra_anterior': j.get_palavra_anterior(),
                    'concluido': j.concluido,
                    'alvo': j.alvo_jogador.nome if j.alvo_jogador else None,
                    'palavras_completas': j.palavras if self.vencedor else [],  # Só mostrar no final
                    'palavras_originais': j.palavras_originais if self.vencedor else []
                } for j in self.jogadores

            ],
            'mensagens_chat': self.mensagens_chat
        }
    
    def get_gabarito_completo(self):
        """Retorna o gabarito completo de todos os jogadores"""
        if not self.vencedor:
            return None
            
        gabarito = {}
        for jogador in self.jogadores:
            gabarito[jogador.nome] = {
                'palavras_originais': jogador.palavras_originais,
                'palavras_normalizadas': jogador.palavras,
                'descobertas': jogador.palavras_descobertas
            }
        
        return gabarito
    
    def reiniciar_jogo(self):
        """Reinicia o jogo mantendo os mesmos jogadores"""
        # Resetar estado da partida
        self.jogo_iniciado = False
        self.vencedor = None
        self.turno_atual = 0
        self.mensagens_chat = []
        
        # Resetar estado dos jogadores
        for jogador in self.jogadores:
            jogador.palavras = []
            jogador.palavras_originais = []
            jogador.dicas = []
            jogador.palavra_atual_index = 1
            jogador.tentativas_erradas_atual = 0
            jogador.tentativas_por_palavra = []
            jogador.palavras_descobertas = []
            jogador.concluido = False
        
        # Reconfigurar alvos
        if len(self.jogadores) >= 2:
            self._configurar_alvos()
        
        return True
