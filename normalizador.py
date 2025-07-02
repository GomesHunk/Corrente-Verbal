import unicodedata
import re

class NormalizadorTexto:
    def __init__(self):
        # Dicionário de correções comuns do português brasileiro
        self.correcoes = {
            # Palavras com til
            'nao': 'não',
            'mae': 'mãe',
            'pao': 'pão',
            'irmao': 'irmão',
            'limao': 'limão',
            'coracoes': 'corações',
            'acoes': 'ações',
            'opcoes': 'opções',
            'informacoes': 'informações',
            'situacoes': 'situações',
            'tradicoes': 'tradições',
            'emocoes': 'emoções',
            'revolucoes': 'revoluções',
            'solucoes': 'soluções',
            'questoes': 'questões',
            'decisoes': 'decisões',
            'impressoes': 'impressões',
            'dimensoes': 'dimensões',
            'extensoes': 'extensões',
            'tensoes': 'tensões',
            'pensoes': 'pensões',
            'mansoes': 'mansões',
            'versoes': 'versões',
            'diversoes': 'diversões',
            'ilusoes': 'ilusões',
            'conclusoes': 'conclusões',
            'exclusoes': 'exclusões',
            'inclusoes': 'inclusões',
            'explosoes': 'explosões',
            'erosoes': 'erosões',
            'corrosoes': 'corrosões',
            'fusoes': 'fusões',
            'confusoes': 'confusões',
            'difusoes': 'difusões',
            'transfusoes': 'transfusões',
            'intrusoes': 'intrusões',
            'extrusoes': 'extrusões',
            'oclusoes': 'oclusões',
            'reclusoes': 'reclusões',
            'seclusoes': 'seclusões',
            'alusoes': 'alusões',
            'ilusoes': 'ilusões',
            'delusoes': 'delusões',
            'colisoes': 'colisões',
            'precisoes': 'precisões',
            'decisoes': 'decisões',
            'incisoes': 'incisões',
            'divisoes': 'divisões',
            'revisoes': 'revisões',
            'previsoes': 'previsões',
            'provisoes': 'provisões',
            'televisoes': 'televisões',
            'supervisoes': 'supervisões',
            'visoes': 'visões',
            'ocasioes': 'ocasiões',
            'persuasoes': 'persuasões',
            'invasoes': 'invasões',
            'evasoes': 'evasões',
            
            # Palavras com acento agudo
            'voce': 'você',
            'cafe': 'café',
            'pe': 'pé',
            'fe': 'fé',
            'cha': 'chá',
            'la': 'lá',
            'ca': 'cá',
            'ja': 'já',
            'so': 'só',
            'nos': 'nós',
            'pos': 'pós',
            'apos': 'após',
            'atraves': 'através',
            'alem': 'além',
            'porem': 'porém',
            'tambem': 'também',
            'ninguem': 'ninguém',
            'alguem': 'alguém',
            'parabens': 'parabéns',
            'refens': 'reféns',
            'armazens': 'armazéns',
            'homens': 'homens',  # já correto
            'jovens': 'jovens',  # já correto
            'viagens': 'viagens',  # já correto
            'imagens': 'imagens',  # já correto
            'mensagens': 'mensagens',  # já correto
            'vantagens': 'vantagens',  # já correto
            'desvantagens': 'desvantagens',  # já correto
            'bagagens': 'bagagens',  # já correto
            'garagens': 'garagens',  # já correto
            'miragens': 'miragens',  # já correto
            'coragens': 'coragens',  # já correto
            'selvagens': 'selvagens',  # já correto
            
            # Palavras com cedilha
            'acao': 'ação',
            'coracao': 'coração',
            'opcao': 'opção',
            'informacao': 'informação',
            'educacao': 'educação',
            'situacao': 'situação',
            'tradicao': 'tradição',
            'emocao': 'emoção',
            'devocao': 'devoção',
            'revolucao': 'revolução',
            'solucao': 'solução',
            'questao': 'questão',
            'decisao': 'decisão',
            'impressao': 'impressão',
            'dimensao': 'dimensão',
            'extensao': 'extensão',
            'tensao': 'tensão',
            'pensao': 'pensão',
            'mansao': 'mansão',
            'versao': 'versão',
            'diversao': 'diversão',
            'ilusao': 'ilusão',
            'conclusao': 'conclusão',
            'exclusao': 'exclusão',
            'inclusao': 'inclusão',
            'explosao': 'explosão',
            'erosao': 'erosão',
            'corrosao': 'corrosão',
            'fusao': 'fusão',
            'confusao': 'confusão',
            'difusao': 'difusão',
            'transfusao': 'transfusão',
            'intrusao': 'intrusão',
            'extrusao': 'extrusão',
            'oclusao': 'oclusão',
            'reclusao': 'reclusão',
            'seclusao': 'seclusão',
            'alusao': 'alusão',
            'delusao': 'delusão',
            'colisao': 'colisão',
            'precisao': 'precisão',
            'incisao': 'incisão',
            'divisao': 'divisão',
            'revisao': 'revisão',
            'previsao': 'previsão',
            'provisao': 'provisão',
            'televisao': 'televisão',
            'supervisao': 'supervisão',
            'visao': 'visão',
            'ocasiao': 'ocasião',
            'persuasao': 'persuasão',
            'invasao': 'invasão',
            'evasao': 'evasão',
            
            # Palavras com acento circunflexo
            'voce': 'você',
            'tres': 'três',
            'mes': 'mês',
            'pes': 'pés',
            'meses': 'meses',  # já correto
            'paises': 'países',
            'ingles': 'inglês',
            'portugues': 'português',
            'frances': 'francês',
            'japones': 'japonês',
            'chines': 'chinês',
            'alemao': 'alemão',
            'interesse': 'interesse',  # já correto
            'interesses': 'interesses',  # já correto
            
            # Palavras comuns com acentos diversos
            'agua': 'água',
            'aguia': 'águia',
            'area': 'área',
            'ideia': 'ideia',  # já correto (nova ortografia)
            'ideias': 'ideias',  # já correto (nova ortografia)
            'heroi': 'herói',
            'heroina': 'heroína',
            'historia': 'história',
            'historias': 'histórias',
            'memoria': 'memória',
            'memorias': 'memórias',
            'vitoria': 'vitória',
            'vitorias': 'vitórias',
            'gloria': 'glória',
            'glorias': 'glórias',
            'categoria': 'categoria',  # já correto
            'categorias': 'categorias',  # já correto
            'secretaria': 'secretaria',  # já correto
            'secretarias': 'secretarias',  # já correto
            'primaria': 'primária',
            'primarias': 'primárias',
            'secundaria': 'secundária',
            'secundarias': 'secundárias',
            'universitaria': 'universitária',
            'universitarias': 'universitárias',
            'necessaria': 'necessária',
            'necessarias': 'necessárias',
            'voluntaria': 'voluntária',
            'voluntarias': 'voluntárias',
            'solitaria': 'solitária',
            'solitarias': 'solitárias',
            'imaginaria': 'imaginária',
            'imaginarias': 'imaginárias',
            'ordinaria': 'ordinária',
            'ordinarias': 'ordinárias',
            'extraordinaria': 'extraordinária',
            'extraordinarias': 'extraordinárias',
            
            # Palavras com trema (antiga ortografia, mas ainda usadas)
            'linguica': 'linguiça',
            'cinquenta': 'cinquenta',  # já correto
            'frequente': 'frequente',  # já correto (nova ortografia)
            'frequencia': 'frequência',
            'consequencia': 'consequência',
            'sequencia': 'sequência',
            'eloquencia': 'eloquência',
            'delinquencia': 'delinquência',
            'tranquilo': 'tranquilo',  # já correto (nova ortografia)
            'tranquilidade': 'tranquilidade',  # já correto (nova ortografia)
            
            # Contrações e palavras compostas comuns
            'dele': 'dele',  # já correto
            'dela': 'dela',  # já correto
            'deles': 'deles',  # já correto
            'delas': 'delas',  # já correto
            'nele': 'nele',  # já correto
            'nela': 'nela',  # já correto
            'neles': 'neles',  # já correto
            'nelas': 'nelas',  # já correto
            'pelo': 'pelo',  # já correto
            'pela': 'pela',  # já correto
            'pelos': 'pelos',  # já correto
            'pelas': 'pelas',  # já correto
            
            # Verbos conjugados comuns
            'esta': 'está',
            'estao': 'estão',
            'sao': 'são',
            'tem': 'tem',  # já correto (singular)
            'teem': 'têm',  # plural (antiga ortografia)
            'tem': 'têm',   # plural (nova ortografia)
            'vem': 'vem',   # já correto (singular)
            'veem': 'vêm',  # plural (antiga ortografia)
            'vem': 'vêm',   # plural (nova ortografia)
            'da': 'dá',     # verbo dar
            'das': 'das',   # já correto (artigo/preposição)
            'de': 'dê',     # verbo dar (imperativo)
            'le': 'lê',     # verbo ler
            'leem': 'leem', # já correto (nova ortografia)
            've': 'vê',     # verbo ver
            'veem': 'veem', # já correto (nova ortografia)
            'creem': 'creem', # já correto (nova ortografia)
            'deem': 'deem',   # já correto (nova ortografia)
            'leem': 'leem',   # já correto (nova ortografia)
            'veem': 'veem',   # já correto (nova ortografia)
            'descreem': 'descreem', # já correto (nova ortografia)
            'releem': 'releem',     # já correto (nova ortografia)
            'preveem': 'preveem',   # já correto (nova ortografia)
            'proveem': 'proveem',   # já correto (nova ortografia)
            'reveem': 'reveem',     # já correto (nova ortografia)
        }
        
        # Padrões regex para identificar tipos de palavras
        self.padroes = {
            'acao_cao': re.compile(r'(.+)cao$'),  # palavras terminadas em -ção
            'plural_oes': re.compile(r'(.+)oes$'),  # plurais terminados em -ões
            'til_ao': re.compile(r'(.+)ao$'),  # palavras terminadas em -ão
        }
    
    def normalizar(self, texto):
        """Normaliza texto aplicando correções automáticas"""
        if not texto:
            return texto
            
        texto_original = texto
        texto = texto.lower().strip()
        
        # 1. Aplicar correções específicas do dicionário
        if texto in self.correcoes:
            return self.correcoes[texto]
        
        # 2. Aplicar padrões regex para correções automáticas
        texto_corrigido = self._aplicar_padroes(texto)
        if texto_corrigido != texto:
            return texto_corrigido
        
        # 3. Se não houver correção, retornar texto original (mantendo capitalização)
        return texto_original.strip()
    
    def _aplicar_padroes(self, texto):
        """Aplica padrões regex para correções automáticas"""
        # Padrão: palavras terminadas em 'cao' -> 'ção'
        if self.padroes['acao_cao'].match(texto) and not texto.endswith('ção'):
            if texto.endswith('cao'):
                return texto[:-3] + 'ção'
        
        # Padrão: palavras terminadas em 'oes' -> 'ões' 
        if self.padroes['plural_oes'].match(texto) and not texto.endswith('ões'):
            if texto.endswith('oes'):
                return texto[:-3] + 'ões'
        
        # Padrão: palavras terminadas em 'ao' -> 'ão'
        if self.padroes['til_ao'].match(texto) and not texto.endswith('ão'):
            if texto.endswith('ao') and len(texto) > 2:
                # Verificar se não é uma palavra que já termina corretamente em 'ao'
                palavras_ao_corretas = ['mao', 'cao', 'sao', 'joao', 'sebastiao']
                if texto not in palavras_ao_corretas:
                    return texto[:-2] + 'ão'
        
        return texto
    
    def comparar_palavras(self, palavra1, palavra2):
        """Compara duas palavras considerando variações de acentos"""
        if not palavra1 or not palavra2:
            return False
            
        # Normalizar ambas as palavras
        norm1 = self.normalizar(palavra1)
        norm2 = self.normalizar(palavra2)
        
        # Comparar versões normalizadas
        if norm1.lower() == norm2.lower():
            return True
        
        # Comparar também versões sem acentos
        sem_acentos1 = self.remover_acentos(norm1.lower())
        sem_acentos2 = self.remover_acentos(norm2.lower())
        
        return sem_acentos1 == sem_acentos2
    
    def remover_acentos(self, texto):
        """Remove acentos de um texto"""
        if not texto:
            return texto
            
        # Normalizar para NFD (decompor caracteres acentuados)
        texto_nfd = unicodedata.normalize('NFD', texto)
        
        # Remover marcas diacríticas (acentos)
        texto_sem_acentos = ''.join(
            char for char in texto_nfd 
            if unicodedata.category(char) != 'Mn'
        )
        
        return texto_sem_acentos
    
    def sugerir_correcao(self, palavra):
        """Sugere uma correção para a palavra se disponível"""
        palavra_lower = palavra.lower().strip()
        
        if palavra_lower in self.correcoes:
            return self.correcoes[palavra_lower]
        
        # Tentar aplicar padrões
        corrigida = self._aplicar_padroes(palavra_lower)
        if corrigida != palavra_lower:
            return corrigida
        
        return None
    
    def foi_corrigida(self, palavra_original, palavra_normalizada):
        """Verifica se a palavra foi corrigida durante a normalização"""
        return palavra_original.lower().strip() != palavra_normalizada.lower().strip()
