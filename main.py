import pygame
import random
import math
import json
import os
import io
import wave
import base64
import zlib
import hashlib
from array import array
from dataclasses import dataclass

# Mixer pequeno para reduzir atraso de som em Android. Se o aparelho nao liberar
# audio, o AudioManager abaixo desativa som sem derrubar o jogo.
pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

APP_TITLE = "O Colosso do Caos"

# ============================================================
# O COLOSSO DO CAOS - V14 WIP PERSONAGENS + EVOLUCAO
# Mobile-first LANDSCAPE: editor de controles, bestiario, builds, Dominios e personagens secretos.
# Controles: toque/mouse + teclado para testes.
# ============================================================

# --- Tela responsiva / LANDSCAPE --------------------------------------------
# Resolucao-alvo do aparelho principal: 2340x1080 (1080x2340 deitado).
# No Android pegamos o framebuffer real. Se o Pydroid/SDL insistir em abrir
# em retrato, o jogo cria uma tela logica horizontal e gira a imagem na saida.
# Assim o layout continua LANDSCAPE e os toques sao convertidos corretamente.
IS_ANDROID = bool(os.environ.get("ANDROID_ARGUMENT") or os.environ.get("P4A_BOOTSTRAP"))
INFO = pygame.display.Info()
ROTATE_OUTPUT = False

if IS_ANDROID:
    DISPLAY = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    PHYS_W, PHYS_H = DISPLAY.get_size()
    if PHYS_W >= PHYS_H:
        SCREEN = DISPLAY
        W, H = PHYS_W, PHYS_H
    else:
        # Framebuffer veio em retrato: desenhamos em landscape e giramos no fim.
        W, H = PHYS_H, PHYS_W
        SCREEN = pygame.Surface((W, H)).convert()
        ROTATE_OUTPUT = True
else:
    # Janela horizontal para testes fora do Android.
    desktop_w = INFO.current_w or 1280
    desktop_h = INFO.current_h or 720
    test_w = min(1280, desktop_w)
    test_h = min(720, desktop_h)
    if test_h >= test_w:
        test_w, test_h = min(1280, desktop_h), min(720, desktop_w)
    DISPLAY = pygame.display.set_mode((test_w, test_h))
    SCREEN = DISPLAY
    W, H = SCREEN.get_size()
    PHYS_W, PHYS_H = W, H

pygame.display.set_caption(APP_TITLE)
CLOCK = pygame.time.Clock()
FPS = 60


def to_game_pos(pos):
    """Converte coordenada fisica do toque/mouse para a tela logica landscape."""
    x, y = pos
    if not ROTATE_OUTPUT:
        return (x, y)
    # SCREEN (W x H) e girada 90 graus no sentido horario para DISPLAY.
    # Inversa de (x_log, y_log) -> (H-y_log, x_log).
    return (y, H - 1 - x)


def present_frame():
    """Apresenta o frame, girando-o quando o Android ficou preso em retrato."""
    if ROTATE_OUTPUT:
        frame = pygame.transform.rotate(SCREEN, -90)
        if frame.get_size() != DISPLAY.get_size():
            frame = pygame.transform.smoothscale(frame, DISPLAY.get_size())
        DISPLAY.blit(frame, (0, 0))
    pygame.display.flip()

# Paleta
BG = (17, 18, 24)
PANEL = (30, 32, 42)
PANEL2 = (43, 46, 59)
WHITE = (240, 242, 247)
GRAY = (155, 160, 175)
DARK = (10, 10, 14)
RED = (224, 67, 76)
GREEN = (85, 211, 121)
BLUE = (77, 151, 255)
YELLOW = (255, 205, 84)
PURPLE = (170, 100, 255)
ORANGE = (255, 142, 61)
CYAN = (85, 225, 230)
PINK = (255, 104, 179)
DIVINE_BLUE = (125, 220, 255)
VASCO_GREEN = (24, 96, 52)
VASCO_NEON = (72, 255, 118)
LIRA_COLOR = (190, 32, 46)
LIRA_ACCENT = (255, 205, 84)  # dourado: contorno, HUD e detalhes da C#nsur#
LIRA_KEY = "Lira Solis, A C#nsur#"
HANK_KEY = "Hank J. Wimbleton"
SUKUNA_KEY = "Sukuna"
RIP_INDRA_KEY = "Rip_Indra"
HISOKA_KEY = "Hisoka Morrow"
RIP_INDRA_COLOR = (232, 234, 238)
HISOKA_COLOR = (255, 112, 190)
HISOKA_REVIVE_COLOR = (196, 28, 126)
SUKUNA_COLOR = (245, 245, 245)
SUKUNA_HAIR = (244, 104, 150)
SUKUNA_SLASH = (235, 72, 92)
SUKUNA_FIRE = (255, 133, 42)
META_ACH_COLOR = (255, 118, 230)

# Assets personalizados da Lira.
# - censured_projectile.png: projétil retangular.
# - censured_form.png: forma totalmente censurada do inimigo.
# Se algum deles nao existir, usa fallback visual sem crashar.
LIRA_CENSORED_PROJECTILE_IMAGE = None
LIRA_CENSORED_FORM_IMAGE = None
HANK_TARGET_IMAGE = None
_LIRA_CENSORED_PROJECTILE_CACHE = {}
_LIRA_CENSORED_FORM_CACHE = {}
_HANK_TARGET_CACHE = {}

def _load_optional_image(candidates):
    for path in candidates:
        try:
            if os.path.exists(path):
                return pygame.image.load(path).convert_alpha()
        except Exception:
            pass
    return None

def _load_lira_images():
    global LIRA_CENSORED_PROJECTILE_IMAGE, LIRA_CENSORED_FORM_IMAGE, HANK_TARGET_IMAGE
    base = os.path.dirname(os.path.abspath(__file__))
    LIRA_CENSORED_PROJECTILE_IMAGE = _load_optional_image((
        os.path.join(base, "assets", "censured_projectile.png"),
        os.path.join(base, "assets", "censured.png"),
        os.path.join(base, "censured_projectile.png"),
        os.path.join(base, "censured.png"),
    ))
    LIRA_CENSORED_FORM_IMAGE = _load_optional_image((
        os.path.join(base, "assets", "censured_form.png"),
        os.path.join(base, "censured_form.png"),
        os.path.join(base, "assets", "censored_form.png"),
        os.path.join(base, "censored_form.png"),
    ))
    HANK_TARGET_IMAGE = _load_optional_image((
        os.path.join(base, "assets", "alvo.png"),
        os.path.join(base, "alvo.png"),
        os.path.join(base, "assets", "target.png"),
        os.path.join(base, "target.png"),
    ))

_load_lira_images()

def _scaled_image(image, cache, size):
    if image is None:
        return None
    size=max(8,int(size))
    if size not in cache:
        try:
            ow,oh=image.get_size(); ratio=oh/max(1,ow)
            cache[size]=pygame.transform.smoothscale(image,(size,max(6,int(size*ratio))))
        except Exception:
            return None
    return cache.get(size)

def censured_projectile_surface(size):
    return _scaled_image(LIRA_CENSORED_PROJECTILE_IMAGE, _LIRA_CENSORED_PROJECTILE_CACHE, size)

def censured_form_surface(size):
    return _scaled_image(LIRA_CENSORED_FORM_IMAGE, _LIRA_CENSORED_FORM_CACHE, size)

def hank_target_surface(size):
    return _scaled_image(HANK_TARGET_IMAGE, _HANK_TARGET_CACHE, size)

# Resolucao-base oficial em LANDSCAPE: 2340x1080.
# Equivale ao aparelho 1080x2340 deitado. Outros tamanhos continuam responsivos.
DESIGN_W = 2340
DESIGN_H = 1080
SCALE = max(0.28, min(W / DESIGN_W, H / DESIGN_H))
SAFE = max(6, int(min(W, H) * 0.018))
# Margens extras para celulares com notch, cantos arredondados e barra de gestos.
CONTROL_SAFE_X = max(SAFE, int(W * 0.030), 34)
CONTROL_SAFE_Y = max(SAFE, int(H * 0.065), 46)

def effective_combat_wave(wave):
    """V14: comprime o antigo endgame. A wave 100 equivale aproximadamente a antiga wave 700."""
    return max(1, int(round(float(wave) * 7.0)))


def enemy_wave_speed_mult(wave):
    """Velocidade quase estavel: a compressao 100 ~= 700 NAO acelera movimento.

    A wave real cresce a velocidade muito devagar e existe um teto de +12%.
    Dificuldade, elites e mecanicas especiais ainda podem aplicar seus proprios
    multiplicadores depois disso.
    """
    return min(1.12, 1.0 + max(0.0, float(wave) - 1.0) * 0.0008)


def high_wave_scaling(wave):
    """Escala V14 usando a wave comprimida apenas para HP/dano.

    Velocidade foi deliberadamente desacoplada para que inimigos de wave alta
    nao comecem parecendo teleportar.
    """
    combat_wave = effective_combat_wave(wave)
    if combat_wave <= 50:
        return 1.0, 1.0, 1.0
    tier = (combat_wave - 50) / 50.0
    hp_mult = 1.0 + 0.35 * tier + 0.080 * tier * tier
    damage_mult = 1.0 + 0.18 * tier + 0.035 * tier * tier
    return hp_mult, damage_mult, 1.0


# V14 WIP 06: o antigo FACIL virou DIFICIL. FACIL/NORMAL sao presets mais tranquilos.
# Recompensas agora premiam risco: Monarca e Impossivel pagam mais que o Normal.
DIFFICULTY_ORDER = ["easy", "normal", "hard", "monarch", "impossible"]
DIFFICULTIES = {
    "easy": {
        "name":"FACIL", "color":GREEN, "hp":0.45, "force":0.60, "damage":0.50, "speed":0.94, "ai":0.60, "count":0.42, "elite":-0.20, "reward":0.75,
        "desc":"Modo mais tranquilo: menos inimigos, menos vida e ataques bem menos agressivos."
    },
    "normal": {
        "name":"NORMAL", "color":CYAN, "hp":0.68, "force":0.80, "damage":0.72, "speed":0.97, "ai":0.78, "count":0.62, "elite":-0.12, "reward":1.00,
        "desc":"Experiencia padrao da V14. Ainda escala forte, mas permite respirar nas primeiras ondas."
    },
    "hard": {
        "name":"DIFICIL", "color":ORANGE, "hp":1.00, "force":1.00, "damage":1.00, "speed":1.00, "ai":1.00, "count":1.00, "elite":0.00, "reward":1.18,
        "desc":"O antigo FACIL da V14. Curva comprimida e endgame chegando cedo, agora com recompensa maior."
    },
    "monarch": {
        "name":"MONARCA", "color":PURPLE, "hp":3.20, "force":1.55, "damage":2.05, "speed":1.28, "ai":1.72, "count":1.38, "elite":0.22, "reward":1.65,
        "desc":"A wave 10 ja deve doer. Inimigos brutais e agressivos, mas as recompensas sobem bastante."
    },
    "impossible": {
        "name":"IMPOSSIVEL", "color":RED, "hp":5.25, "force":1.85, "damage":2.70, "speed":1.40, "ai":2.10, "count":1.55, "elite":0.32, "reward":2.10,
        "desc":"Cada acerto inimigo tira 10% do HP maximo e drena Estamina. O maior risco paga o maior premio."
    },
}


def difficulty_cfg(key):
    return DIFFICULTIES.get(key, DIFFICULTIES["easy"])


# ============================================================
# V14 WIP 08 - MODOS DE JOGO
# Cada modo muda a regra central da run; dificuldade continua sendo
# um preset separado aplicado por cima, exceto onde a propria regra
# do modo exige comportamento especial.
# ============================================================
GAME_MODE_MAIN = ["normal", "infinite", "boss_rush", "arena_survival", "extinction", "evolution"]
GAME_MODE_SECRET = ["rogue", "one_vs_all", "glonk_hunt"]
GAME_MODE_ORDER = GAME_MODE_MAIN + GAME_MODE_SECRET
GAME_MODES = {
    "normal": {"name":"PADRAO", "color":WHITE, "desc":"Waves, upgrades, eventos, Pecados e Glonk. A experiencia base."},
    "infinite": {"name":"INFINITO", "color":CYAN, "desc":"Sem fim. A cada 10 waves escolha uma de duas MALDICOES permanentes."},
    "boss_rush": {"name":"BOSS RUSH", "color":RED, "desc":"Somente bosses. Cada vitoria deixa uma Heranca no proximo."},
    "arena_survival": {"name":"ARENA", "color":ORANGE, "desc":"Spawn continuo, recompensas por KOs e perigos sem pausar a luta."},
    "extinction": {"name":"EXTINCAO", "color":GRAY, "desc":"Voce comeca forte, mas CURA nao existe. Todo dano fica ate o fim."},
    "evolution": {"name":"EVOLUCAO", "color":GREEN, "desc":"A cada wave os inimigos ganham uma evolucao permanente e acumulativa."},
    "rogue": {"name":"ROGUE", "color":PURPLE, "desc":"Personagem, regra da wave e ordem de bosses ficam imprevisiveis."},
    "one_vs_all": {"name":"UM CONTRA TODOS", "color":YELLOW, "desc":"Todos os outros personagens jogaveis aparecem como bosses, um por um."},
    "glonk_hunt": {"name":"CACA AO GLONK", "color":GREEN, "desc":"Todo round tem Glonk. A cada wave ele aprende truques novos para fugir."},
}

INFINITE_CURSES = [
    ("horde", "HORDA SEM FIM", "+20% de inimigos por wave"),
    ("boss_hp", "REIS OBESOS", "Bosses recebem +30% de HP"),
    ("enemy_hp", "CARNE DEMAIS", "Todos os inimigos recebem +20% de HP"),
    ("enemy_damage", "MAOS PESADAS", "Inimigos causam +15% de dano"),
    ("elite", "LINHAGEM PODRE", "+12% de chance de Elite"),
    ("stamina", "PULMAO AMALDICOADO", "Sua regeneracao de Estamina cai 20%"),
    ("domain", "RITUAL QUEBRADO", "Carga de Dominio recebida cai 20%"),
]

EVOLUTION_TRAITS = [
    ("carapace", "CARAPACA", "+12% HP inimigo"),
    ("claws", "GARRAS", "+10% dano inimigo"),
    ("instinct", "INSTINTO", "+3% velocidade inimiga"),
    ("mind", "MENTE", "+10% frequencia de ataques"),
    ("mutation", "MUTACAO", "+5% quantidade e chance de Elite"),
    ("regeneration", "REGENERACAO", "Inimigos recuperam 0,35% do HP por segundo"),
    ("explosive", "ULTIMO PRESENTE", "Mais inimigos podem nascer Explosivos"),
]

ROGUE_RULES = [
    ("frenzy", "PROJETO FRENESI", "Inimigos atacam 35% mais rapido"),
    ("thick", "CARNE EXTRA", "Inimigos recebem +35% HP nesta wave"),
    ("glass", "VIDRO DUPLO", "Jogador e inimigos causam mais dano nesta wave"),
    ("elite", "SO TEM MUTANTE", "Chance de Elite explode nesta wave"),
    ("glonk", "VERDE DEMAIS", "Glonk tem 10% de chance nesta wave"),
    ("swarm", "SUPERPOPULACAO", "+45% inimigos nesta wave"),
]

def S(v):
    return max(1, int(v * SCALE))

FONT_S = pygame.font.Font(None, S(34))
FONT_M = pygame.font.Font(None, S(46))
FONT_L = pygame.font.Font(None, S(70))
FONT_XL = pygame.font.Font(None, S(96))

# Fonte com maior chance de suportar os caracteres estilizados do titulo.
# V8: fonte padrao do Pygame no titulo/subtitulo para evitar caracteres quebrados no Android.
FONT_TITLE = pygame.font.Font(None, S(78))
FONT_FANCY_S = pygame.font.Font(None, S(30))


class AudioManager:
    """Audio procedural: nenhum arquivo externo e necessario.

    Os efeitos e loops sao sintetizados em memoria no inicio. Em aparelhos sem
    mixer/audio disponivel, todos os metodos viram no-op para evitar crashes.
    """
    def __init__(self, settings):
        self.sample_rate = 22050
        self.enabled = False
        # V14 FINAL: volume real de 0 a 100 salvo nas CONFIGURACOES.
        # Saves antigos continuam compativeis: ON/OFF antigo vira volume padrao ou zero.
        legacy_sfx_on = bool(settings.get("sfx_on", True))
        legacy_music_on = bool(settings.get("music_on", True))
        self.sfx_volume = max(0.0, min(1.0, float(settings.get("sfx_volume", 70 if legacy_sfx_on else 0)) / 100.0))
        self.music_volume = max(0.0, min(1.0, float(settings.get("music_volume", 30 if legacy_music_on else 0)) / 100.0))
        self.sfx_on = self.sfx_volume > 0.0001
        self.music_on = self.music_volume > 0.0001
        self.current_track = None
        self.last_play = {}
        self.sfx = {}
        self.music = {}
        self.music_channel = None
        # V14 MUSIC: temas externos opcionais.
        # Se os arquivos nao existirem, o jogo usa a trilha procedural antiga.
        self.audio_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "audio")
        self.external_music_files = {
            "menu": os.path.join(self.audio_dir, "menu.ogg"),
            "battle": os.path.join(self.audio_dir, "batalha.ogg"),
            "mahoraga_summon": os.path.join(self.audio_dir, "mahoraga_summon.ogg"),
            "mahoraga_battle": os.path.join(self.audio_dir, "mahoraga_battle.ogg"),
            "sukuna_ult": os.path.join(self.audio_dir, "ultsukuna.ogg"),
            "sukuna_destruction": os.path.join(self.audio_dir, "destruicaosukuna.ogg"),
            "sukuna_domain": os.path.join(self.audio_dir, "sukuna_domain.ogg"),
        }
        self.external_music_failed = set()
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=self.sample_rate, size=-16, channels=1, buffer=512)
            pygame.mixer.set_num_channels(24)
            pygame.mixer.set_reserved(1)  # canal 0 fica exclusivo para a musica
            self.music_channel = pygame.mixer.Channel(0)
            self._build_sounds()
            self.enabled = True
        except Exception:
            self.enabled = False

    def _sound_from_samples(self, samples):
        if not samples:
            samples = [0]
        pcm = array('h', [max(-32767, min(32767, int(v))) for v in samples])
        bio = io.BytesIO()
        with wave.open(bio, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(pcm.tobytes())
        bio.seek(0)
        return pygame.mixer.Sound(bio)

    def _tone(self, freq=440, duration=0.15, volume=0.5, end_freq=None, noise=0.0, attack=0.01, release=0.06):
        n = max(1, int(duration * self.sample_rate))
        out = []
        phase = 0.0
        for i in range(n):
            t = i / self.sample_rate
            p = i / max(1, n - 1)
            f = freq if end_freq is None else freq + (end_freq - freq) * p
            phase += math.tau * f / self.sample_rate
            env_a = min(1.0, t / max(0.001, attack))
            remain = duration - t
            env_r = min(1.0, remain / max(0.001, release))
            env = max(0.0, min(env_a, env_r))
            val = math.sin(phase) * volume
            if noise:
                val += random.uniform(-1.0, 1.0) * noise
            out.append(val * env * 32767)
        return self._sound_from_samples(out)

    def _chord(self, freqs, duration=0.35, volume=0.25, descend=0.0):
        n = max(1, int(duration * self.sample_rate))
        phases = [0.0 for _ in freqs]
        out = []
        for i in range(n):
            t = i / self.sample_rate
            p = i / max(1, n - 1)
            env = min(1.0, t / 0.02) * min(1.0, (duration-t) / 0.10)
            v = 0.0
            for j, f0 in enumerate(freqs):
                f = max(30.0, f0 * (1.0 - descend * p))
                phases[j] += math.tau * f / self.sample_rate
                v += math.sin(phases[j])
            v /= max(1, len(freqs))
            out.append(v * volume * env * 32767)
        return self._sound_from_samples(out)

    def _music_loop(self, mood="arena"):
        # Loop curto estilo chiptune/arcade, leve o bastante para ser gerado no celular.
        duration = 3.2
        n = int(duration * self.sample_rate)
        if mood == "boss":
            root, beat, amp = 73.42, 0.20, 0.17
            pattern = [1.0, 1.0, 1.189, 1.0, 1.335, 1.189, 1.0, 0.891]
        elif mood == "menu":
            root, beat, amp = 110.0, 0.40, 0.11
            pattern = [1.0, 1.26, 1.50, 1.26, 1.0, 1.19, 1.50, 1.19]
        else:
            root, beat, amp = 98.0, 0.25, 0.14
            pattern = [1.0, 1.50, 1.26, 1.50, 1.12, 1.50, 1.26, 1.68]
        out = []
        for i in range(n):
            t = i / self.sample_rate
            step = int(t / beat) % len(pattern)
            local = (t % beat) / beat
            env = max(0.0, 1.0 - local * 1.4)
            f = root * pattern[step]
            bass = math.sin(math.tau * (root/2) * t) * 0.55
            lead = math.sin(math.tau * f * t) * env
            pulse = math.sin(math.tau * (f*2) * t) * env * 0.18
            if mood == "boss":
                thump = math.sin(math.tau * 46 * t) * (max(0.0, 1.0 - ((t % beat)/beat)*4.0)) * 0.65
            else:
                thump = 0.0
            fade = min(1.0, t/0.03, (duration-t)/0.03)
            out.append((bass + lead + pulse + thump) * amp * max(0.0, fade) * 32767)
        return self._sound_from_samples(out)

    def _build_sounds(self):
        # Ataques/personagens
        self.sfx["ana_staff"] = self._tone(520, 0.19, 0.34, 900, noise=0.025)
        self.sfx["ana_explode"] = self._tone(150, 0.24, 0.55, 58, noise=0.25, release=0.12)
        self.sfx["kevyn_sword"] = self._tone(720, 0.13, 0.28, 170, noise=0.22, release=0.08)
        self.sfx["execute"] = self._tone(260, 0.24, 0.55, 75, noise=0.16, release=0.12)
        self.sfx["kayk_dual"] = self._tone(980, 0.10, 0.32, 420, noise=0.12, release=0.05)
        self.sfx["ycaro_shotgun"] = self._tone(180, 0.18, 0.50, 62, noise=0.38, release=0.10)
        self.sfx["hank_cannon"] = self._tone(105, 0.28, 0.70, 42, noise=0.42, release=0.14)
        self.sfx["hank_blast"] = self._tone(72, 0.36, 0.78, 30, noise=0.48, release=0.20)

        # Movimento/combate
        self.sfx["dash"] = self._tone(240, 0.17, 0.25, 720, noise=0.14)
        self.sfx["perfect"] = self._chord([660, 990], 0.18, 0.28)
        self.sfx["parry"] = self._chord([880, 1320, 1760], 0.20, 0.35)
        self.sfx["hurt"] = self._tone(170, 0.18, 0.35, 85, noise=0.20)
        self.sfx["shield"] = self._chord([300, 600, 900], 0.15, 0.22)
        self.sfx["hit"] = self._tone(320, 0.06, 0.18, 220, noise=0.16, release=0.03)
        self.sfx["enemy_die"] = self._tone(240, 0.16, 0.25, 80, noise=0.12)
        self.sfx["revive"] = self._chord([220, 330, 440, 660], 0.55, 0.35)

        # Pickups/progressao
        self.sfx["heal"] = self._chord([520, 660, 780], 0.22, 0.25)
        self.sfx["stamina"] = self._chord([440, 700, 980], 0.20, 0.23)
        self.sfx["pickup"] = self._tone(700, 0.10, 0.22, 1050)
        self.sfx["upgrade"] = self._chord([392, 523, 659], 0.38, 0.28)
        self.sfx["synergy"] = self._chord([220, 440, 660, 880], 0.60, 0.30)
        self.sfx["wave_clear"] = self._chord([330, 440, 550], 0.34, 0.24)
        self.sfx["unlock"] = self._chord([392, 494, 587, 784], 0.75, 0.32)

        # Grandes eventos/UI
        self.sfx["domain"] = self._chord([82, 164, 246, 492], 0.70, 0.38, descend=0.10)
        self.sfx["boss"] = self._chord([65, 98, 130], 0.72, 0.42, descend=0.22)
        self.sfx["death"] = self._chord([330, 247, 196], 0.65, 0.32, descend=0.28)
        self.sfx["glonk"] = self._tone(540, 0.72, 0.32, 55, noise=0.05, release=0.20)
        self.sfx["click"] = self._tone(620, 0.07, 0.16, 760, release=0.03)
        self.sfx["pause"] = self._tone(330, 0.10, 0.18, 260)

        self.music["menu"] = self._music_loop("menu")
        self.music["arena"] = self._music_loop("arena")
        self.music["boss"] = self._music_loop("boss")

    def play(self, name, volume=1.0, cooldown_ms=0):
        if not self.enabled or not self.sfx_on:
            return
        snd = self.sfx.get(name)
        if snd is None:
            return
        now = pygame.time.get_ticks()
        last = self.last_play.get(name, -999999)
        if cooldown_ms and now - last < cooldown_ms:
            return
        self.last_play[name] = now
        try:
            ch = pygame.mixer.find_channel(True)
            ch.set_volume(clamp(self.sfx_volume * volume, 0.0, 1.0))
            ch.play(snd)
        except Exception:
            pass

    def toggle_sfx(self):
        # Mantido apenas para compatibilidade interna; a UI usa sliders 0-100.
        self.sfx_on = not self.sfx_on
        if self.sfx_on and self.sfx_volume <= 0.0001:
            self.sfx_volume = 0.70
        elif not self.sfx_on:
            self.sfx_volume = 0.0
        return self.sfx_on

    def set_sfx_volume(self, percent):
        percent = int(clamp(percent, 0, 100))
        self.sfx_volume = percent / 100.0
        self.sfx_on = percent > 0
        return percent

    def set_music_volume(self, percent):
        percent = int(clamp(percent, 0, 100))
        self.music_volume = percent / 100.0
        self.music_on = percent > 0
        if not self.music_on:
            self._stop_music_everywhere()
        else:
            # Atualiza imediatamente qualquer faixa que ja esteja tocando.
            try:
                pygame.mixer.music.set_volume(self.music_volume)
            except Exception:
                pass
            try:
                if self.music_channel is not None:
                    self.music_channel.set_volume(self.music_volume)
            except Exception:
                pass
        return percent

    def _stop_music_everywhere(self):
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        try:
            if self.music_channel is not None:
                self.music_channel.stop()
        except Exception:
            pass
        self.current_track = None

    def _try_external_music(self, role, volume):
        """Tenta tocar menu.ogg/batalha.ogg via streaming. Retorna True se ativo."""
        path = self.external_music_files.get(role)
        if not path or path in self.external_music_failed or not os.path.isfile(path):
            return False
        key = "file:" + os.path.abspath(path)
        try:
            # Se esta faixa ja esta tocando, so atualiza o volume.
            if self.current_track == key and pygame.mixer.music.get_busy():
                pygame.mixer.music.set_volume(clamp(volume, 0.0, 1.0))
                return True

            # Evita a faixa procedural tocar junto com a musica externa.
            if self.music_channel is not None:
                self.music_channel.stop()
            try:
                pygame.mixer.music.fadeout(180)
            except Exception:
                pygame.mixer.music.stop()
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(clamp(volume, 0.0, 1.0))
            pygame.mixer.music.play(-1)
            self.current_track = key
            return True
        except Exception as exc:
            # Um arquivo ruim nao pode derrubar o jogo: marca e volta para a musica procedural.
            print("Falha ao carregar musica externa:", path, exc)
            self.external_music_failed.add(path)
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            self.current_track = None
            return False

    def play_external_once(self, role, volume=1.0):
        """Toca um arquivo externo UMA vez usando o stream do mixer.

        Usado pela cutscene do Mahoraga: voz/uivos/CLANK nao devem entrar em loop.
        """
        if not self.enabled:
            return False
        path = self.external_music_files.get(role)
        if not path or path in self.external_music_failed or not os.path.isfile(path):
            return False
        key = "file-once:" + os.path.abspath(path)
        try:
            if self.music_channel is not None:
                self.music_channel.stop()
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(clamp(volume, 0.0, 1.0))
            pygame.mixer.music.play(0)
            self.current_track = key
            return True
        except Exception as exc:
            print("Falha ao carregar audio externo unico:", path, exc)
            self.external_music_failed.add(path)
            self.current_track = None
            return False

    def toggle_music(self):
        # Mantido apenas para compatibilidade interna; a UI usa sliders 0-100.
        self.music_on = not self.music_on
        if self.music_on and self.music_volume <= 0.0001:
            self.music_volume = 0.30
        elif not self.music_on:
            self.music_volume = 0.0
        if not self.music_on and self.enabled:
            self._stop_music_everywhere()
        return self.music_on

    def sync_music(self, game):
        if not self.enabled or self.music_channel is None:
            return

        # A invocacao do Mahoraga usa o stream principal como audio de cutscene.
        # Nao deixe a musica normal reiniciar por cima dela. Esse audio obedece ao volume de EFEITOS.
        if (getattr(game, "mahoraga_cutscene_active", False) or
                getattr(game, "sukuna_cutscene_active", False) or
                getattr(game, "sukuna_destruction_active", False)):
            try:
                if self.sfx_on and self.current_track and self.current_track.startswith("file-once:"):
                    pygame.mixer.music.set_volume(clamp(self.sfx_volume, 0.0, 1.0))
                elif not self.sfx_on and self.current_track and self.current_track.startswith("file-once:"):
                    pygame.mixer.music.set_volume(0.0)
            except Exception:
                pass
            return

        if not self.music_on:
            self._stop_music_everywhere()
            return

        in_battle = game.state in ("playing", "paused", "run_upgrades", "upgrade", "curse_choice", "vinicius_mega", "lira_domain_choice") or (game.state == "settings" and getattr(game, "settings_return_state", "menu") == "paused")
        if in_battle:
            dimmed = game.state in ("paused", "run_upgrades", "vinicius_mega") or (game.state == "settings" and getattr(game, "settings_return_state", "menu") == "paused")
            vol = self.music_volume * (0.42 if dimmed else 1.0)
            # Santuário Malevolente: o tema enviado pelo usuario assume a musica durante os 8s.
            # Quando o dominio acaba, o fluxo normal abaixo restaura batalha.ogg/Mahoraga automaticamente.
            if (getattr(game, "domain_active", False) and
                    getattr(getattr(game, "player", None), "character", None) == SUKUNA_KEY):
                if self._try_external_music("sukuna_domain", vol):
                    return
            # Mahoraga vivo ganha trilha propria ate cair.
            maho = getattr(game, "mahoraga", None)
            if maho is not None and not getattr(maho, "dead", True):
                if self._try_external_music("mahoraga_battle", vol):
                    return
            # V14 FINAL: a mesma batalha.ogg continua tocando durante TODA a run, inclusive entre waves.
            if self._try_external_music("battle", vol):
                return
            boss_alive = any((type(e).__name__ == "Boss" or getattr(e, "is_glonk_boss", False)) and not getattr(e, "dead", False) for e in game.enemies)
            target = "boss" if boss_alive else "arena"
        else:
            vol = self.music_volume * 0.82
            if self._try_external_music("menu", vol):
                return
            target = "menu"

        # Fallback: musica procedural original, caso os .ogg ainda nao estejam na pasta.
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            self.music_channel.set_volume(vol)
            if target != self.current_track or not self.music_channel.get_busy():
                self.music_channel.stop()
                self.music_channel.play(self.music[target], loops=-1)
                self.current_track = target
        except Exception:
            pass


CHARACTER_CONFIG = {
    "Ana": {
        "hp": 82, "stamina": 118, "weapon": 3, "weapon_name": "CAJADO", "damage": 10.0, "speed": 315,
        "regen": 11.5, "color": PINK, "domain": "REALIDADE SEM SAIDA",
        "desc": "Pouco HP | Cajado | Invoca mini-Anas explosivas",
        "domain_desc": "Cajado recarrega em 1s e as explosoes ficam muito mais fortes",
    },
    "Kevyn": {
        "hp": 240, "stamina": 190, "weapon": 0, "weapon_name": "ESPADA", "damage": 18.0, "speed": 250,
        "regen": 9.0, "color": BLUE, "domain": "TRONO FORA DO TEMPO",
        "desc": "MUITO HP + estamina | Espada | Resistente",
        "domain_desc": "Invulneravel e 2x velocidade dentro da area",
    },
    "Ycaro": {
        "hp": 135, "stamina": 132, "weapon": 2, "weapon_name": "SHOTGUN", "damage": 16.0, "speed": 288,
        "regen": 10.0, "color": ORANGE, "domain": "CAMPO DE CACA DO ZUMBI",
        "desc": "Equilibrado | Shotgun | Medio alcance",
        "domain_desc": "Mira automatica e quase sem cooldown dentro da area",
    },
    "Kayk": {
        "hp": 125, "stamina": 155, "weapon": 4, "weapon_name": "PISTOLAS DUPLAS", "damage": 15.0, "speed": 300,
        "regen": 11.0, "color": PURPLE, "domain": "NECROPOLE DAS ALMAS",
        "desc": "Duas pistolas | Dois tiros por ataque | Desbloqueavel",
        "domain_desc": "Almas atacam automaticamente os inimigos dentro da area",
    },
    "Pedro": {
        "hp": 132, "stamina": 148, "weapon": 6, "weapon_name": "ABACAXI BUMERANGUE", "damage": 18.0, "speed": 295,
        "regen": 10.5, "color": YELLOW, "domain": "X DA COLHEITA",
        "desc": "Abacaxi bumerangue | Vai e volta | Controle de area",
        "domain_desc": "Cada ataque lanca abacaxis nas 4 diagonais formando um X",
    },
    "Ruan": {
        "hp": 158, "stamina": 152, "weapon": 7, "weapon_name": "INVESTIDA", "damage": 21.0, "speed": 305,
        "regen": 10.0, "color": CYAN, "domain": "REINO DOS AMIGOS",
        "desc": "Ataca com dash | Abates diretos viram amigos",
        "domain_desc": "Invoca um guardiao amigo e regenera HP/Estamina dentro da area",
    },
    "Colosso do Caos": {
        "hp": 225, "stamina": 182, "weapon": 8, "weapon_name": "GOLPE EM AREA", "damage": 28.0, "speed": 270,
        "regen": 9.5, "color": (220, 220, 220), "domain": "AUTORIDADE DO CAOS",
        "desc": "Golpe circular gigante | Personagem secreto final",
        "domain_desc": "Elimina instantaneamente todos os inimigos dentro da area",
    },
    "Sans": {
        "hp": 1, "stamina": 180, "weapon": 9, "weapon_name": "OSSOS / BLASTER", "damage": 19.0, "speed": 315,
        "regen": 14.0, "color": (235, 240, 255), "domain": "BAD TIME",
        "desc": "1 HP | Esquiva por Estamina | Ossos | Blaster dedicado",
        "domain_desc": "Arena azul: ossos automaticos, obstaculos giratorios e Blasters a cada 2s",
    },
    "Strikada Egoísta": {
        "hp": 145, "stamina": 150, "weapon": 10, "weapon_name": "CHUTE DIRETO!", "damage": 22.0, "speed": 305,
        "regen": 10.5, "color": (125, 220, 255), "domain": "METAVISAO DO CADEADO AZUL",
        "desc": "Bola ricocheteia entre inimigos | Atacante de longo alcance",
        "domain_desc": "Projeteis inimigos ficam lentos e a bola pode quicar infinitamente dentro da area",
    },
    "Glonk 100% Power": {
        "hp": 1, "stamina": 100, "weapon": 11, "weapon_name": "GOLPE DE 1 DANO", "damage": 1.0, "speed": 285,
        "regen": 9.0, "color": GREEN, "domain": "NENHUM",
        "desc": "Consegue andar e atacar | 1 HP | 1 de dano base",
        "domain_desc": "Glonk 100% Power nao possui Expansao de Dominio",
    },
    "Potential Man": {
        "hp": 105, "stamina": 155, "weapon": 12, "weapon_name": "CAO DIVINO", "damage": 20.0, "speed": 292,
        "regen": 10.5, "color": (18, 18, 24), "domain": "MAHORAGA",
        "desc": "Invoca 2 Caes Divinos | Sapos | ULT: Mahoraga",
        "domain_desc": "Invoca Mahoraga: adaptativo, resistente e perigoso para TODOS",
    },
    "Vinicius 13": {
        "hp": 138, "stamina": 150, "weapon": 13, "weapon_name": "AUTOMACAO V13", "damage": 12.0, "speed": 300,
        "regen": 10.5, "color": (220, 55, 70), "domain": "NENHUM",
        "desc": "Projeteis encadeados | Sucata Inimiga | Mini e Mega Torretas",
        "domain_desc": "Vinicius 13 troca Dominio por um sistema de construcao automatica.",
    },
    "Vasco": {
        "hp": 142, "stamina": 162, "weapon": 14, "weapon_name": "FICHA DA APOSTA", "damage": 20.0, "speed": 298,
        "regen": 10.5, "color": VASCO_GREEN, "domain": "I JUST HIT THE JACKPOT",
        "desc": "O Apostador Incansavel | Aposta altera o dano | Jackpot de 8s",
        "domain_desc": "Toda aposta fica positiva; ao chegar a 100%, o Dominio quebra e ativa o JACKPOT.",
    },
    LIRA_KEY: {
        "hp": 126, "stamina": 158, "weapon": 15, "weapon_name": "CENSURA", "damage": 8.0, "speed": 302,
        "regen": 11.0, "color": LIRA_COLOR, "domain": "&#$*%@!??",
        "desc": "A C#nsur# | Ataques fracos removem atributos | censured.png",
        "domain_desc": "Escolha 2 censuras; afeta todos que estavam dentro e Lira recebe o oposto como buff.",
    },
    HANK_KEY: {
        "hp": 175, "stamina": 135, "weapon": 16, "weapon_name": "CANHAO PESADO", "damage": 24.0, "speed": 246,
        "regen": 9.0, "color": (92, 92, 92), "domain": "SEJA BEM VINDO (OU NAO)",
        "desc": "Carga parado 1.5s | Tanque lento | ULT com 10 marcacoes de artilharia",
        "domain_desc": "Segure DOM 3s: prende inimigos, 2x velocidade, regenera Estamina e troca o canhao por facas duplas.",
    },
    SUKUNA_KEY: {
        "hp": 155, "stamina": 165, "weapon": 17, "weapon_name": "CORTES AMALDICOADOS", "damage": 22.0, "speed": 292,
        "regen": 10.5, "color": SUKUNA_COLOR, "domain": "SANTUARIO MALEVOLENTE",
        "desc": "Cortes lancados | ULT Fuuga | Passiva: Dedos do Sukuna",
        "domain_desc": "Segure ULT por 3s: barreira aberta por 8s; todos os inimigos recebem cortes continuos.",
    },
    RIP_INDRA_KEY: {
        "hp": 168, "stamina": 158, "weapon": 18, "weapon_name": "TRUE TRIPLE YORU", "damage": 24.0, "speed": 286,
        "regen": 10.0, "color": RIP_INDRA_COLOR, "domain": "ADM SPAWN ZONE",
        "desc": "BETA | TTK tripla | Clique: corte largo | Segure: 3 ondas carregadas | QUEST: 50% das conquistas",
        "domain_desc": "Dominio fechado enorme: velocidade de ataque aumenta brutalmente e o dano dobra.",
    },
    HISOKA_KEY: {
        "hp": 132, "stamina": 165, "weapon": 19, "weapon_name": "BUNGE-GUM", "damage": 16.0, "speed": 304,
        "regen": 11.0, "color": HISOKA_COLOR, "domain": "AS DO BARALHO",
        "desc": "BETA | Cartas bumerangue | Bombeia-Gum revive 1x | QUEST: Wave 30 Impossivel com 3 nao-principais",
        "domain_desc": "Cartas teleguiadas atingem todos dentro do Dominio com dano extremo.",
    },
    "Glonk": {
        "hp": 100, "stamina": 0, "weapon": 5, "weapon_name": "NADA", "damage": 0.0, "speed": 0,
        "regen": 0.0, "color": GREEN, "domain": "NENHUM",
        "desc": "não faz nada e morre",
        "domain_desc": "Glonk nao possui expansao de dominio",
    },
}

# ============================================================
# V13 - PROGRESSAO INDIVIDUAL DE PERSONAGENS
# Cada ponto de evolucao pertence ao personagem que o encontrou.
# O nivel e 1 + a soma dos pontos distribuidos nos seis status.
# ============================================================
CHARACTER_ORDER = ["Ana", "Kevyn", "Ycaro", "Kayk", "Pedro", "Ruan", "Vasco", LIRA_KEY, HANK_KEY, "Potential Man", "Colosso do Caos", "Strikada Egoísta", "Glonk 100% Power", "Vinicius 13", "Glonk"]
BETA_CHARACTER_ORDER = ["Sans", SUKUNA_KEY, RIP_INDRA_KEY, HISOKA_KEY]
EVOLUTION_STAT_KEYS = ["strength", "speed", "resistance", "hp", "stamina", "parry"]
EVOLUTION_STAT_LABELS = {
    "strength": "FORCA",
    "speed": "VELOCIDADE",
    "resistance": "RESISTENCIA",
    "hp": "HP",
    "stamina": "ESTAMINA",
    "parry": "PARRY",
}
EVOLUTION_STAT_DESCS = {
    "strength": "+3% de dano base por ponto",
    "speed": "+1,5% de velocidade por ponto",
    "resistance": "-1,5% de dano recebido por ponto",
    "hp": "+6 de HP maximo por ponto",
    "stamina": "+5 STA e +1,5% regen por ponto",
    "parry": "+0,006s de janela e -1,5% cooldown",
}
MAX_EVOLUTION_STAT = 25
CHARACTER_BASE_RATINGS = {
    "Ana": {"strength":6,"speed":8,"resistance":3,"hp":4,"stamina":7,"parry":5},
    "Kevyn": {"strength":7,"speed":5,"resistance":9,"hp":9,"stamina":9,"parry":7},
    "Ycaro": {"strength":6,"speed":7,"resistance":6,"hp":6,"stamina":6,"parry":6},
    "Kayk": {"strength":7,"speed":8,"resistance":5,"hp":6,"stamina":8,"parry":5},
    "Pedro": {"strength":7,"speed":7,"resistance":6,"hp":6,"stamina":7,"parry":7},
    "Ruan": {"strength":8,"speed":8,"resistance":7,"hp":7,"stamina":7,"parry":6},
    "Colosso do Caos": {"strength":9,"speed":6,"resistance":9,"hp":9,"stamina":8,"parry":5},
    "Glonk": {"strength":1,"speed":1,"resistance":1,"hp":1,"stamina":1,"parry":1},
    "Strikada Egoísta": {"strength":8,"speed":8,"resistance":6,"hp":6,"stamina":7,"parry":6},
    "Glonk 100% Power": {"strength":1,"speed":6,"resistance":1,"hp":1,"stamina":4,"parry":2},
    "Sans": {"strength":7,"speed":9,"resistance":8,"hp":1,"stamina":10,"parry":9},
    "Potential Man": {"strength":7,"speed":7,"resistance":7,"hp":7,"stamina":7,"parry":6},
    "Vinicius 13": {"strength":5,"speed":7,"resistance":5,"hp":6,"stamina":7,"parry":5},
    "Vasco": {"strength":7,"speed":8,"resistance":6,"hp":7,"stamina":8,"parry":6},
    LIRA_KEY: {"strength":4,"speed":8,"resistance":5,"hp":6,"stamina":8,"parry":6},
    HANK_KEY: {"strength":8,"speed":4,"resistance":9,"hp":8,"stamina":6,"parry":5},
    SUKUNA_KEY: {"strength":9,"speed":7,"resistance":7,"hp":7,"stamina":8,"parry":6},
    RIP_INDRA_KEY: {"strength":9,"speed":7,"resistance":7,"hp":8,"stamina":7,"parry":7},
    HISOKA_KEY: {"strength":7,"speed":9,"resistance":6,"hp":6,"stamina":8,"parry":8},
}

# ============================================================
# V15 - POWER UPS 2.0: TAGS + UNIVERSAIS COMPATIVEIS + ASSINATURAS
# ============================================================
# Cada personagem possui tags invisiveis. Power Ups universais/hibridos so entram
# na roleta quando o kit realmente consegue usar o efeito.
CHARACTER_TAGS = {
    "Ana": {"PROJECTILE", "SUMMON", "DASH", "DOMAIN", "PARRY"},
    "Kevyn": {"MELEE", "PARRY", "DASH", "DOMAIN"},
    "Ycaro": {"PROJECTILE", "SHOTGUN", "DOMAIN", "PARRY"},
    "Kayk": {"PROJECTILE", "DASH", "DOMAIN", "PARRY"},
    "Pedro": {"PROJECTILE", "BOOMERANG", "DOMAIN", "PARRY"},
    "Ruan": {"MELEE", "SUMMON", "DASH", "DOMAIN", "PARRY"},
    "Colosso do Caos": {"MELEE", "AOE", "DOMAIN", "PARRY"},
    "Sans": {"PROJECTILE", "MELEE", "DASH", "DOMAIN"},
    "Strikada Egoísta": {"PROJECTILE", "BALL", "DOMAIN", "PARRY"},
    "Glonk 100% Power": {"MELEE", "PARRY"},
    "Potential Man": {"MELEE", "SUMMON", "DOMAIN", "PARRY"},
    "Vinicius 13": {"PROJECTILE", "TURRET", "SUMMON", "PARRY"},
    "Vasco": {"PROJECTILE", "DOMAIN", "PARRY"},
    LIRA_KEY: {"PROJECTILE", "DOMAIN", "PARRY"},
    HANK_KEY: {"PROJECTILE", "MELEE", "TURRET", "DOMAIN", "PARRY"},
    SUKUNA_KEY: {"PROJECTILE", "AOE", "DOMAIN", "PARRY"},
    RIP_INDRA_KEY: {"MELEE", "PROJECTILE", "AOE", "DOMAIN", "PARRY"},
    HISOKA_KEY: {"PROJECTILE", "BOOMERANG", "DOMAIN", "PARRY"},
    "Glonk": set(),
}

# Requisitos de compatibilidade para cartas universais antigas e novas.
# O primeiro mapa exige TODAS as tags; o segundo aceita QUALQUER uma delas.
UPGRADE_TAG_REQUIREMENTS = {
    "pierce": {"PROJECTILE"},
    "profane_ricochet": {"PROJECTILE"},
    "ghost_dash": {"DASH"},
    "domain_evolution": {"DOMAIN"},
    "devil_pact": {"DOMAIN"},
    "explosive_parry": {"PARRY"},
    "blade_vampire": {"MELEE"},
    "chaotic_ammo": {"PROJECTILE"},
    "supreme_command": {"SUMMON"},
    "inertia": {"DASH"},
    "overpressure": {"AOE"},
    "resonant_domain": {"DOMAIN"},
    "auto_loader": {"TURRET"},
}
UPGRADE_TAG_ANY = {
    "kinetic_rebound": {"BALL", "BOOMERANG"},
}

def upgrade_compatible(card, character):
    key = card[3]
    tags = CHARACTER_TAGS.get(character, set())
    required = UPGRADE_TAG_REQUIREMENTS.get(key, set())
    any_required = UPGRADE_TAG_ANY.get(key, set())
    if required and not required.issubset(tags):
        return False
    if any_required and not (tags & any_required):
        return False
    return True

# Cartas globais: so aparecem quando as tags permitem aproveitar o efeito.
UNIVERSAL_UPGRADES = [
    ("common", "CORACAO REFORCADO", "+20 HP maximo e cura 20", "heart_reinforced"),
    ("common", "PULMAO DE ACO", "+20 Estamina maxima", "steel_lung"),
    ("common", "SEGUNDO FOLEGO", "+25% regeneracao de Estamina", "second_wind"),
    ("common", "MAO PESADA", "+15% de dano", "heavy_hand"),
    ("common", "PES LIGEIROS", "+10% velocidade", "quick_feet"),
    ("common", "CATADOR", "+8% chance total de orbes", "scavenger"),

    ("rare", "SEDE DE BATALHA", "Abates recuperam 5 Estamina", "battle_thirst"),
    ("rare", "HEMOGLOBINA DUVIDOSA", "Orb de HP tambem recupera Estamina", "questionable_hemo"),
    ("rare", "OVERCLOCK", ">80% Estamina: +20% dano e velocidade", "overclock"),
    ("rare", "ULTIMO SUSPIRO", "<25% HP: regeneracao de Estamina 2x", "last_breath"),
    ("rare", "PARRY EXPLOSIVO", "Projeteis rebatidos explodem ao acertar", "explosive_parry"),
    ("rare", "PREDADOR", "Abate concede +25% dano por 3s", "predator"),
    ("rare", "PERFURANTE", "+1 perfuracao nos projeteis", "pierce"),
    ("rare", "MIRA CRITICA", "+12% chance de critico (critico base x1,5)", "crit"),
    ("rare", "MAOS FIRMES", "+12% velocidade de ataque", "steady_hands"),
    ("rare", "MEDICO DE CAMPO", "Ao limpar uma wave, recupera 5% do HP maximo", "field_medic"),
    ("rare", "MAQUINA DE COMBO", "Combo demora mais para desaparecer", "combo_engine"),

    ("epic", "DASH FANTASMA", "Dash deixa uma copia que explode", "ghost_dash"),
    ("epic", "DIVIDA DE SANGUE", "Sem Estamina? Habilidade pode cobrar HP", "blood_debt"),
    ("epic", "CORACAO VAMPIRICO", "A cada 8 hits de combo, cura HP", "vampire_heart"),
    ("epic", "CHUVA DE ORBES", "Elites sempre deixam uma orb principal", "orb_rain"),
    ("epic", "RICOCHETE PROFANO", "Projeteis podem saltar para outro inimigo", "profane_ricochet"),
    ("epic", "EXECUCAO EM CADEIA", "Executar marca outra presa; mate-a para curar", "chain_execution"),
    ("epic", "ALEM DO LIMITE", "Estamina pode sobrecarregar ate 130%", "beyond_limit"),

    ("legendary", "SEGUNDA BARRA", "Revive 1x com 40% HP e uma explosao", "second_bar"),
    ("legendary", "TEMPO PARTIDO", "Perfect Dodge desacelera inimigos", "broken_time"),
    ("legendary", "CACADOR DE GIGANTES", "+40% dano em boss, gigantes e tanques", "giant_hunter"),
    ("legendary", "BURACO NEGRO DE ORBES", "Atrai orbes; 3 seguidas causam explosao", "orb_black_hole"),
    ("legendary", "COMBO ETERNO", "Tomar dano corta o combo pela metade", "eternal_combo"),
    ("legendary", "EVOLUCAO SUPREMA", "Seu Dominio ganha um segundo efeito", "domain_evolution"),

    ("cursed", "CANHAO DE VIDRO", "+100% dano, mas -35% HP maximo", "glass_cannon"),
    ("cursed", "FOME INSACIAVEL", "Abates curam; orbes de HP deixam de curar", "insatiable_hunger"),
    ("cursed", "PACTO DO DIABO", "Dominio carrega 2x; ativar custa 12% HP", "devil_pact"),
    ("cursed", "SEM FREIOS", "+40% dano/velocidade, mas recebe +25% dano", "no_brakes"),
    ("cursed", "UM ULTIMO JOGO", "Revive 1x mais forte; sem cura naquela onda", "one_last_game"),
    ("cursed", "DEUS NAO ESTA OLHANDO", "<20% HP: dano e velocidade absurdos", "god_not_watching"),
]

# Power Ups hibridos: aparecem somente para um pequeno grupo definido pelas tags.
HYBRID_UPGRADES = [
    ("epic", "LAMINA VAMPIRICA", "CORPO-A-CORPO: a cada 6 acertos, cura 4% do HP maximo", "blade_vampire"),
    ("epic", "MUNICAO CAOTICA", "PROJETIL: 18% dos impactos causam +60% dano", "chaotic_ammo"),
    ("legendary", "COMANDO SUPREMO", "SUMMON: invocacoes ganham +25% dano e velocidade", "supreme_command"),
    ("rare", "INERCIA", "DASH: depois de usar Dash, +25% dano por 2s", "inertia"),
    ("epic", "SOBREPRESSAO", "AREA: abates por golpes em area soltam uma onda menor", "overpressure"),
    ("legendary", "DOMINIO RESSONANTE", "DOMINIO: +1,5s de duracao e +15% dano dentro dele", "resonant_domain"),
    ("epic", "AUTO-LOADER", "TORRETA: torretas recarregam 25% mais rapido", "auto_loader"),
    ("epic", "REBOTE CINETICO", "BOLA/BUMERANGUE: +1 quique/retorno ofensivo e +15% velocidade", "kinetic_rebound"),
]

# Power Ups de Assinatura. Os antigos continuam existindo e os novos abaixo
# tornam cada build bem mais propria do personagem.
CHARACTER_UPGRADES = {
    "Ana": [
        ("rare", "CORRIDA CURTA", "+45% dano se a mini-Ana viajar bastante", "ana_blind_spot"),
        ("rare", "EXPLOSAO DE FASE", "+35% raio das explosoes do cajado", "ana_phase_bullet"),
        ("rare", "CLONAGEM BARATA", "Cada uso do cajado invoca +1 mini-Ana", "ana_double_shot"),
        ("epic", "ERRO NA REALIDADE", "20% chance da explosao acontecer duas vezes", "ana_reality_error"),
        ("epic", "CACADORAS IMPOSSIVEIS", "Mini-Anas ficam muito mais rapidas", "ana_impossible_shot"),
        ("epic", "PASSO VETORIAL", "Dash mais longo e recarrega mais rapido", "ana_vector_step"),
        ("legendary", "OLHO CAUSAL", "Explosoes distantes podem causar criticos brutais", "ana_causal_eye"),
        ("legendary", "REALIDADE.EXE", "Dominio fortalece perseguicao, raio e explosoes", "ana_reality_exe"),
        ("epic", "EXERCITO DE BOLSO", "+1 Mini-Ana por uso, respeitando o limite normal", "ana_pocket_army"),
        ("legendary", "ERRO DE CONTINUIDADE", "Mini-Ana que explode tem 30% de chance de gerar outra perto da Ana", "ana_continuity"),
        ("divine", "SOMOS TODAS ANA", "Mini-Anas proximas compartilham alvo e aceleram em grupo", "ana_all_ana"),
        ("rare", "REALIDADE INSTAVEL", "A cada 5 Mini-Anas, a proxima nasce gigante e causa 2x dano", "ana_unstable_reality"),
    ],
    "Kevyn": [
        ("rare", "LAMINA LARGA", "+35% alcance da espada", "kevyn_wide_blade"),
        ("rare", "RUPTURA", "Ataques de espada custam -1 Estamina", "kevyn_rupture"),
        ("rare", "PESO IMPOSSIVEL", "+25% dano de espada", "kevyn_impossible_weight"),
        ("epic", "MURALHA HUMANA", "Mais HP tambem fortalece a espada", "kevyn_human_wall"),
        ("epic", "CONTRA-ATAQUE TEMPORAL", "Parry perfeito cria um corte ao redor", "kevyn_time_counter"),
        ("epic", "IMOVEL COMO O FIM", "Parado por 0.8s: recebe 45% menos dano", "kevyn_immovable"),
        ("legendary", "ESPADA FAMINTA", "A cada 3 abates de espada, cura HP", "kevyn_hungry_sword"),
        ("legendary", "O TEMPO NAO PASSA POR MIM", "Dominio devolve projeteis congelados", "kevyn_time_stops"),
        ("rare", "SEGUNDO CORTE", "Todo ataque tem 25% de chance de repetir o corte", "kevyn_second_cut"),
        ("epic", "LAMINA SEDENTA", "Derrotar com a espada reduz brutalmente o cooldown do proximo ataque", "kevyn_thirsty_blade"),
        ("legendary", "PARRY ABSOLUTO", "Parry perfeito fortalece brutalmente o proximo corte", "kevyn_absolute_parry"),
        ("divine", "UM CONTRA CEM", "Quanto mais inimigos perto, maior o alcance e dano da espada", "kevyn_one_vs_hundred"),
    ],
    "Ycaro": [
        ("rare", "QUEIMA-ROUPA", "+55% dano de shotgun bem de perto", "ycaro_point_blank"),
        ("rare", "MAIS CHUMBO", "+2 pellets por disparo", "ycaro_more_pellets"),
        ("rare", "POLVORA ALTA", "+25% velocidade e alcance dos pellets", "ycaro_hot_powder"),
        ("epic", "EFEITO DOMINO", "Abate de shotgun explode e machuca proximos", "ycaro_domino"),
        ("epic", "RECARGA AGRESSIVA", "Cada pellet acertado devolve Estamina", "ycaro_aggressive_reload"),
        ("epic", "CANO SERRADO", "Mais espalhamento, mas muito mais dano perto", "ycaro_sawed_off"),
        ("legendary", "CACADOR", "Shotgun recebe assistencia de mira leve", "ycaro_hunter"),
        ("legendary", "NAO EXISTE PERTO DEMAIS", "Dominio: chumbo extra e dano brutal perto", "ycaro_no_too_close"),
        ("rare", "CHUMBO GROSSO", "Menos pellets; eles ficam maiores e muito mais fortes", "ycaro_heavy_lead"),
        ("epic", "DOZE CANOS", "30% de chance de disparar uma segunda shotgun logo depois", "ycaro_twelve_barrels"),
        ("legendary", "CACADOR FERIDO", "Quanto menor o HP, menor o espalhamento da shotgun", "ycaro_wounded_hunter"),
        ("divine", "SALA ERRADA", "Acertos a queima-roupa arremessam inimigos contra outros", "ycaro_wrong_room"),
    ],
    "Kayk": [
        ("rare", "GATILHOS GEMEOS", "As pistolas disparam +1 par de balas", "kayk_extra_pair"),
        ("rare", "ALMA PERFURANTE", "+1 perfuracao nos tiros de Kayk", "kayk_soul_pierce"),
        ("rare", "COBRANCA FUNEBRE", "Abates recuperam +7 Estamina", "kayk_funeral_tax"),
        ("epic", "ECO DOS MORTOS", "Tiros ganham chance alta de ricochetear", "kayk_dead_echo"),
        ("epic", "PASSO ESPECTRAL", "Dash de Kayk fica mais longo e barato", "kayk_spectral_step"),
        ("epic", "MUNICAO POSTUMA", "+30% dano das pistolas", "kayk_posthumous_ammo"),
        ("legendary", "CORTEJO ARMADO", "Dominio dispara almas com mais frequencia", "kayk_armed_procession"),
        ("legendary", "MIL ALMAS, DOIS GATILHOS", "Dominio dispara mais almas e causa mais dano", "kayk_thousand_souls"),
        ("rare", "FOGO CRUZADO", "Algumas rajadas disparam balas laterais", "kayk_crossfire"),
        ("epic", "MARCADO PELA ALMA", "Acertos repetidos marcam o alvo; o proximo tiro explode a marca", "kayk_soul_mark"),
        ("legendary", "DOIS GATILHOS, UM ALVO", "As pistolas focam automaticamente inimigos com pouca vida", "kayk_two_triggers"),
        ("divine", "PROCISSAO BALISTICA", "Inimigo derrotado deixa uma alma-armada que dispara uma bala", "kayk_ballistic_procession"),
    ],
    "Pedro": [
        ("rare", "FRUTA MADURA", "+30% dano dos abacaxis", "pedro_ripe_fruit"),
        ("rare", "TRAJETORIA ESPINHOSA", "+30% velocidade e alcance do bumerangue", "pedro_spiny_path"),
        ("rare", "IDA E VOLTA", "Dano na volta +35%", "pedro_round_trip"),
        ("epic", "ABACAXI EXPLOSIVO", "Cada impacto causa dano em area", "pedro_explosive_pineapple"),
        ("epic", "DUPLA COLHEITA", "Ataques normais lancam +1 abacaxi", "pedro_double_harvest"),
        ("epic", "CASCA DE ACO", "Parry custa menos Estamina e dura mais", "pedro_steel_peel"),
        ("legendary", "COROA DO ABACAXI", "Acertos na volta causam dano critico aumentado", "pedro_pineapple_crown"),
        ("legendary", "X DO DESTINO", "Dominio tambem lanca nas 4 direcoes cardeais", "pedro_x_destiny"),
        ("rare", "EFEITO SATURNO", "O abacaxi faz uma volta curta ao redor de Pedro antes de retornar", "pedro_saturn"),
        ("epic", "COLHEITA DUPLA", "Ao voltar, 30% de chance de lancar outro abacaxi imediatamente", "pedro_double_crop"),
        ("legendary", "FRUTA PREDADORA", "Depois do primeiro acerto, procura automaticamente outro inimigo", "pedro_predator_fruit"),
        ("divine", "PLANTACAO INDUSTRIAL", "Abacaxis que erram ficam plantados e explodem quando alguem encosta", "pedro_industrial_plantation"),
    ],
    "Ruan": [
        ("rare", "INVESTIDA BRUTAL", "+30% dano do ataque-dash", "ruan_brutal_charge"),
        ("rare", "PACTO DOS AMIGOS", "+50% HP para os amigos", "ruan_fallen_pact"),
        ("rare", "FORCA DO BANDO", "+35% dano dos amigos", "ruan_pack_hunger"),
        ("epic", "COMANDO DE GUERRA", "+35% velocidade dos amigos", "ruan_war_command"),
        ("epic", "PASSO DO NECROMANTE", "Ataque-dash fica mais longo e rapido", "ruan_necro_step"),
        ("epic", "GRUPO CRESCENTE", "Amigos nascem com escudo extra", "ruan_growing_army"),
        ("legendary", "GUARDA REAL", "O guardiao do Dominio fica muito mais forte", "ruan_royal_guard"),
        ("legendary", "REI ENTRE MORTOS", "Dominio regenera ainda mais HP e Estamina", "ruan_king_dead"),
        ("rare", "RECRUTAMENTO FORCADO", "Abates por Dash podem gerar um segundo Amigo enfraquecido", "ruan_forced_recruitment"),
        ("epic", "FORMACAO DE ATAQUE", "Amigos proximos uns dos outros ganham dano e velocidade", "ruan_attack_formation"),
        ("legendary", "NAO DEIXAMOS NINGUEM PRA TRAS", "Quando um Amigo morre, os outros entram em furia", "ruan_no_one_left"),
        ("divine", "EXERCITO SEM FIM", "A cada 5 kills diretas do Ruan nasce um Amigo fraco extra", "ruan_endless_army"),
    ],
    "Colosso do Caos": [
        ("rare", "ONDA DO CAOS", "+25% raio do golpe em area", "father_wave"),
        ("rare", "IMPACTO SISMICO", "+30% dano do golpe em area", "father_slap"),
        ("rare", "FOLEGO COLOSSAL", "+30 Estamina maxima", "father_lung"),
        ("epic", "AUTORIDADE", "Golpe em area apaga projeteis inimigos", "father_authority"),
        ("epic", "CAOS CRESCENTE", "+55% dano contra bosses", "father_family_issues"),
        ("epic", "COLOSSO PRESENTE", "Derrotar boss recupera 30% do HP", "father_present"),
        ("legendary", "CIRCULO DA SENTENCA", "+35% raio da Expansao", "father_sentence_circle"),
        ("legendary", "PONTO FINAL", "Expansao tambem enche HP e Estamina", "father_final_word"),
        ("rare", "AUTORIDADE CRESCENTE", "Cada inimigo acertado aumenta o raio do proximo ataque", "father_growing_authority"),
        ("epic", "IMPACTO REINCIDENTE", "Sobreviventes recebem um segundo impacto menor 1s depois", "father_repeat_slap"),
        ("legendary", "SOBERANIA DO CAOS", "Atingidos ficam mais lentos e causam menos dano", "father_i_rule_here"),
        ("divine", "SENTENCA DO CAOS", "Matar 3+ inimigos no mesmo golpe cria uma segunda onda de choque", "father_paternal_sentence"),
    ],
    "Vinicius 13": [
        ("rare", "SUCATA PREMIUM", "Precisa de 4 kills em vez de 5 para tentar construir Mini-Torre", "vinicius_premium_scrap"),
        ("epic", "MANUTENCAO AUTOMATICA", "Torretas recuperam HP depois de alguns segundos sem dano", "vinicius_auto_maintenance"),
        ("legendary", "LINHA DE PRODUCAO", "Construir torre tem 30% de chance de criar outra com 50% HP", "vinicius_production_line"),
        ("divine", "ISSO QUE E AUTOMATICO", "Quando Vinicius acerta, todas as torres ofensivas atacam imediatamente", "vinicius_truly_automatic"),
    ],
    "Strikada Egoísta": [
        ("rare", "REBOTE EGOISTA", "+2 inimigos no limite de quique da bola", "strikada_more_bounces"),
        ("rare", "VISAO DE GOL", "A bola corrige a rota e persegue o inimigo mais proximo", "strikada_homing"),
        ("epic", "DOIS PROTAGONISTAS", "Cada Chute Direto lanca duas bolas", "strikada_two_balls"),
        ("epic", "GOL DE IMPACTO", "Se a bola derrotar um inimigo, ele explode e causa dano em area", "strikada_kill_explosion"),
        ("rare", "PASSE PRA MIM MESMO", "Depois do ultimo quique, a bola retorna e o proximo chute recarrega mais rapido", "strikada_self_pass"),
        ("epic", "METAVISAO", "A bola prioriza inimigos com menos HP", "strikada_metavision"),
        ("legendary", "O PROTAGONISTA SOU EU", "Cada quique consecutivo aumenta o dano da bola", "strikada_protagonist"),
        ("divine", "GOL IMPOSSIVEL", "3+ abates com uma bola deixam a proxima com quiques infinitos por alguns segundos", "strikada_impossible_goal"),
    ],
    "Glonk 100% Power": [
        ("rare", "2% POWER", "+100% dano. Sim: 1 vira 2.", "glonk_2_power"),
        ("epic", "LINGUA INDUSTRIAL", "O golpe de lingua fica muito mais largo e comprido", "glonk_industrial_tongue"),
        ("legendary", "GLONK APRENDEU", "Cada kill aumenta permanentemente o dano em +1 nesta run", "glonk_learned"),
        ("divine", "101% POWER", "Uma vez por wave, o primeiro ataque causa dano absurdamente maior", "glonk_101_power"),
    ],
    "Vasco": [
        ("rare", "FICHA MARCADA", "Resultados positivos ficam mais provaveis fora do Dominio", "vasco_marked_chip"),
        ("epic", "APOSTA ALTA", "Acima de 70% de Aposta ganha +30% dano; abaixo de 30% ganha velocidade", "vasco_high_stakes"),
        ("legendary", "SEQUENCIA DE SETES", "3 vitorias seguidas concedem +20% de Aposta", "vasco_sevens"),
        ("divine", "A CASA SEMPRE PERDE", "Jackpot dura +2s e toda run comeca com 60% de Aposta", "vasco_house_loses"),
    ],
    LIRA_KEY: [
        ("rare", "TARJA ESPESSA", "Projeteis de censura ficam maiores e aplicam mais censura", "lira_thick_bar"),
        ("epic", "QUATRO PALAVRAS PROIBIDAS", "25% dos acertos censuram dois atributos de uma vez", "lira_four_words"),
        ("legendary", "PAGINA RASGADA", "Inimigos totalmente censurados recebem +50% dano", "lira_torn_page"),
        ("divine", "NADA SERA PUBLICADO", "A Expansao permite escolher 3 censuras em vez de 2", "lira_nothing_published"),
    ],
    HANK_KEY: [
        ("rare", "MUNICAO DE ALTO CALIBRE", "+25% raio das explosoes do canhao", "hank_high_caliber"),
        ("epic", "CICLO DE FERROLHO", "Carga parado cai para 1,1s e o canhao recarrega mais rapido", "hank_bolt_cycle"),
        ("legendary", "ALVO CONFIRMADO", "Tiro que chega ao limite sem acertar explode com +50% dano", "hank_confirmed_target"),
        ("divine", "MADNESS COMBAT", "No Dominio: facas +50% dano e canhao automatico dispara mais rapido", "hank_madness_combat"),
    ],
    "Potential Man": [
        ("rare", "MATILHA COORDENADA", "Caes Divinos ganham +20% dano e velocidade", "potential_coordinated_pack"),
        ("epic", "SOMBRA ANFIBIA", "Sapos desaceleram inimigos atingidos por 2s", "potential_amphibian_shadow"),
        ("legendary", "RODA PREMATURA", "Mahoraga nasce com 20% de Adaptacao", "potential_early_wheel"),
        ("divine", "GENERAL DAS DEZ SOMBRAS", "Invocacoes ganham +40% dano e cooldown dos Caes cai pela metade", "potential_ten_shadows_general"),
    ],
    SUKUNA_KEY: [
        ("rare", "DESMANTELAR", "Cortes ficam maiores, mais rapidos e viajam mais", "sukuna_dismantle"),
        ("epic", "CORTE ADAPTATIVO", "Acertos consecutivos no mesmo alvo aumentam o dano dos cortes", "sukuna_adaptive_cut"),
        ("legendary", "FORNALHA ABERTA", "Fuuga ganha +35% dano e +20% raio", "sukuna_open_furnace"),
        ("divine", "REI DAS MALDICOES", "Boss derrotado pode conceder um dedo extra e o Santuário causa +25% dano", "sukuna_king_curses"),
    ],
    "Sans": [
        ("rare", "OSSO TEIMOSO", "Ossos corrigem levemente a rota para o alvo", "sans_stubborn_bone"),
        ("epic", "ATALHO AZUL", "Dash custa menos e recarrega 30% mais rapido", "sans_blue_shortcut"),
        ("legendary", "JULGAMENTO KARMICO", "Blaster causa +50% dano", "sans_karmic_judgement"),
        ("divine", "PIOR TEMPO", "BAD TIME dura +3s e ossos automaticos aparecem mais rapido", "sans_worse_time"),
    ],
    RIP_INDRA_KEY: [
        ("rare", "TUSHITA QUEST", "+30% de dano com a True Triple Yoru e suas ondas", "rip_tushita_quest"),
        ("epic", "ADMIN ABUSE", "+25% alcance dos cortes e +10% dano", "rip_admin_abuse"),
        ("legendary", "TRIPLA AUTORIDADE", "Carga maxima chega mais rapido e ondas carregadas ganham +1 perfuracao", "rip_triple_authority"),
        ("divine", "ADMIN RAGE", "Ondas da TTK ficam muito mais rapidas e explodem em uma area enorme no impacto", "rip_admin_rage"),
    ],
    HISOKA_KEY: [
        ("rare", "TRUQUE DE BARALHO", "Clique dispara +1 carta em leque", "hisoka_card_trick"),
        ("epic", "GOMA ELASTICA", "Cartas voltam mais rapido e causam +40% dano na volta", "hisoka_elastic_gum"),
        ("legendary", "CORINGA PARALISANTE", "Carta carregada fica 50% maior e paralisa por 2s", "hisoka_paralyzing_joker"),
        ("divine", "O SHOW DEVE CONTINUAR", "Bombeia-Gum revive mais forte; Aranha Excitante dispara 8 cartas", "hisoka_show_must_go_on"),
    ],
    "Glonk": [
        ("rare", "GLONK CORRE", "Glonk descobre que pernas existem e ganha muita velocidade", "glonk_runs"),
        ("epic", "NAO ERA PRA EU ESTAR AQUI", "Ganha 1 escudo no inicio de cada wave", "glonk_not_supposed"),
        ("legendary", "COVARDIA PROFISSIONAL", "Projeteis inimigos ficam 25% mais lentos enquanto Glonk foge", "glonk_professional_coward"),
        ("divine", "GLONK, O ULTIMO", "Uma vez por run, um golpe letal deixa Glonk com 1 HP", "glonk_last_one"),
    ],
}

# Definicoes de sinergia tambem alimentam a aba SINERGIAS do catalogo.
UPGRADE_SYNERGIES = [
    ({"explosive_parry", "broken_time"}, "PARADOXO BALISTICO", "Parry explosivo tambem desacelera inimigos."),
    ({"ycaro_point_blank", "ycaro_more_pellets"}, "EXECUCAO BALISTICA", "Shotgun ganha +1 pellet e dano extra de perto."),
    ({"ana_impossible_shot", "ana_reality_error"}, "GEOMETRIA IMPOSSIVEL", "Mini-Anas ficam ainda mais rapidas e instaveis."),
    ({"kevyn_human_wall", "kevyn_time_counter"}, "FORTALEZA DO FIM", "Contra-ataques escalam melhor com a resistencia do Kevyn."),
    ({"blood_debt", "last_breath"}, "PACTO DE SOBREVIVENCIA", "Regeneracao de Estamina aumenta ainda mais em perigo."),
    ({"pedro_round_trip", "pedro_explosive_pineapple"}, "COLHEITA DE GUERRA", "Abacaxi ganha +15% dano e explosoes melhores."),
    ({"ruan_brutal_charge", "ruan_fallen_pact"}, "MARCHA DOS AMIGOS", "Amigos recebem +15% dano adicional."),
    ({"ana_pocket_army", "ana_continuity"}, "REALIDADE RECURSIVA", "Mini-Anas recriadas ganham +25% velocidade."),
    ({"kevyn_second_cut", "kevyn_absolute_parry"}, "DOIS CORTES, UM INSTANTE", "Segundo Corte herda metade do bonus do Parry Absoluto."),
    ({"kayk_soul_mark", "kayk_ballistic_procession"}, "FUNERAL EM RAJADA", "Explodir uma marca fortalece a alma-armada seguinte."),
    ({"hank_high_caliber", "hank_bolt_cycle"}, "ARTILHARIA DE BOLSO", "Explosoes do Hank ficam maiores e o canhao recarrega ainda mais rapido."),
    ({"sukuna_adaptive_cut", "sukuna_open_furnace"}, "COZINHA MALEVOLENTE", "Cortes adaptativos fortalecem levemente o proximo Fuuga."),
    ({"rip_admin_abuse", "rip_admin_rage"}, "PERMISSAO DE ADMIN", "Explosoes das ondas ganham +20% de raio."),
    ({"hisoka_elastic_gum", "hisoka_paralyzing_joker"}, "NAO E MAGIA", "Cartas carregadas retornam e puxam o alvo na volta."),
]

STACKABLE_UPGRADES = {"heart_reinforced", "steel_lung", "second_wind", "heavy_hand", "quick_feet", "scavenger", "pierce", "crit"}

FATHER_UNLOCK_CHARACTERS = ["Ana", "Kevyn", "Ycaro", "Kayk", "Pedro", "Ruan"]

BOSS_VARIANTS = [
    {
        "key": "father", "name": "O COLOSSO DO CAOS", "color": (160, 50, 70),
        "domain": "CIRCULO DO CAOS",
        "domain_desc": "Ondas caoticas causam dano periodico em quem ficar perto demais.",
        "desc": "Boss da onda 5. Avanca, investe e dispara rajadas circulares.",
    },
    {
        "key": "devourer", "name": "O DEVORADOR", "color": (120, 50, 160),
        "domain": "ESTOMAGO SEM FUNDO",
        "domain_desc": "Drena Estamina rapidamente; sem Estamina, passa a drenar HP.",
        "desc": "Boss faminto que pressiona o jogador com rajadas e drenagem de recursos.",
    },
    {
        "key": "sentinel", "name": "A SENTINELA", "color": (55, 130, 180),
        "domain": "OLHO DO CERCO",
        "domain_desc": "Cria disparos extras em cruz enquanto o jogador estiver na area.",
        "desc": "Boss de controle de area, focado em projeteis e posicionamento.",
    },
    {
        "key": "void", "name": "REI DO VAZIO", "color": (65, 65, 82),
        "domain": "SILENCIO ABSOLUTO",
        "domain_desc": "Quase bloqueia regeneracao de Estamina e reduz carga de Dominio.",
        "desc": "Boss tardio que enfraquece recursos e pune partidas longas.",
    },
]

BESTIARY_ENTRIES = [
    {"name":"Glonk", "type":"Inimigo Raro", "hp":"4x HP medio da wave", "speed":"Fugitivo", "damage":"Nao ataca", "desc":"Uma criatura extremamente covarde que evita qualquer confronto direto. Quando avistado, tentara manter a maior distancia possivel do jogador. Recomendacao: nao deixe para depois.", "glonk_training":True},
    {"name":"Glonk, O Ultimo", "type":"Boss Secreto", "hp":"???", "speed":"███████", "damage":"███████", "desc":"Voce deixou para depois. Agora ele esta muito emotivo.", "glonk_training":True, "hidden_key":"glonk_last_discovered"},
    {"name":"PERSEGUIDOR", "type":"Inimigo", "hp":"1.15x HP base", "speed":"1.15x velocidade", "damage":"Contato: 7 + 0.7/onda", "desc":"Corre diretamente ate voce e tenta manter contato."},
    {"name":"ATIRADOR", "type":"Inimigo", "hp":"1.00x HP base", "speed":"0.72x velocidade", "damage":"Projetil: 7 + 0.55/onda", "desc":"Mantem distancia e dispara projeteis em intervalos regulares."},
    {"name":"KITER", "type":"Inimigo", "hp":"0.85x HP base", "speed":"1.05x velocidade", "damage":"2 projeteis: 5 + 0.45/onda", "desc":"Anda de lado, foge quando voce chega perto e atira em pares."},
    {"name":"TANQUE", "type":"Inimigo", "hp":"2.40x HP base", "speed":"0.58x velocidade", "damage":"Contato: 1.45x", "desc":"Lento, enorme e resistente. Excelente candidato a Execucao."},
    {"name":"ELITE: FRENESI", "type":"Mutacao", "hp":"HP do hospedeiro", "speed":"1.55x", "damage":"Normal", "desc":"Mutacao rosa extremamente rapida."},
    {"name":"ELITE: GIGANTE", "type":"Mutacao", "hp":"2.10x", "speed":"Normal", "damage":"1.30x contato", "desc":"Aumenta muito HP, tamanho e dano de contato."},
    {"name":"ELITE: BLINDADO", "type":"Mutacao", "hp":"1.65x HP", "speed":"Normal", "damage":"Normal", "desc":"Recebe apenas 72% do dano causado pelo jogador."},
    {"name":"ELITE: EXPLOSIVO", "type":"Mutacao", "hp":"HP normal", "speed":"Normal", "damage":"Explode em 8 projeteis", "desc":"Ao morrer dispara uma coroa de projeteis perigosos."},
    {"name":"O COLOSSO DO CAOS", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Contato alto + rajadas", "desc":"Boss da onda 5. Seu Dominio e CIRCULO DO CAOS."},
    {"name":"O DEVORADOR", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Contato + drenagem", "desc":"Seu Dominio ESTOMAGO SEM FUNDO devora Estamina e depois HP."},
    {"name":"A SENTINELA", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Controle por projeteis", "desc":"Seu Dominio OLHO DO CERCO cria disparos extras em cruz."},
    {"name":"REI DO VAZIO", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Pressao de recursos", "desc":"SILENCIO ABSOLUTO reduz regeneracao e carga de Dominio."},
    {"name":"A GULA", "type":"Boss Especial", "hp":"Escala brutal + memoria de derrotas", "speed":"Aumenta a cada encontro", "damage":"Qualquer golpe que atravesse sua defesa encerra a run", "desc":"No novo ciclo V14, a Gula aparece primeiro na onda 80. Cada vez que devora um jogador, fica permanentemente mais forte nos reencontros."},
    {"name":"MINI-ANA", "type":"Invocacao", "hp":"Explode ao contato", "speed":"Persegue automaticamente", "damage":"Explosao da Ana", "desc":"Criada pelo cajado da Ana. Corre ate o alvo e explode em area."},
    {"name":"AMIGO DO RUAN", "type":"Invocacao", "hp":"Depende do inimigo recrutado", "speed":"Persegue inimigos", "damage":"Ataque automatico", "desc":"Nasce quando Ruan derrota diretamente um inimigo. Certas armas podem copiar completamente o inimigo derrotado."},
    {"name":"GUARDIAO DO RUAN", "type":"Invocacao", "hp":"Muito alto", "speed":"Alta", "damage":"Corpo a corpo pesado", "desc":"Guardiao criado pela Expansao de Ruan e preso a area do Dominio."},
    {"name":"CAES DIVINOS", "type":"Invocacao Beta", "hp":"HP proprio + regeneracao", "speed":"Alta", "damage":"Mordidas automaticas", "desc":"Dupla invocada pelo Potential Man ao segurar ATK. So enfrenta Mahoraga se o jogador provocar Mahoraga primeiro."},
    {"name":"MAHORAGA", "type":"Invocacao Beta", "hp":"Muito alto + cura por onda", "speed":"Boss", "damage":"Lamina do Exterminio", "desc":"Entidade neutra e adaptativa. Adapta +10% por onda ate 80%: resistencia contra todos e dano adaptado somente contra o jogador."},
    {"name":"MINI TORRETAS V13", "type":"Invocacao", "hp":"125 + escala", "speed":"Paradas", "damage":"Varia por modelo", "desc":"Cura, Aleatoria, Disparo ou Muralha. Vinicius 13 pode manter ate 5 em campo."},
    {"name":"HOSPITAL-AUTOMATICO", "type":"Invocacao", "hp":"Mega", "speed":"Parada", "damage":"Suporte", "desc":"Mega torre que cura somente torretas em qualquer ponto da arena."},
    {"name":"CANHAO ANTI-TITA", "type":"Invocacao", "hp":"Mega", "speed":"Parada", "damage":"50% do alvo forte", "desc":"Mega torre que atira uma pedra a cada 5s no inimigo mais forte e causa dano em area."},
    {"name":"BALISTICA AUTOMATICA", "type":"Invocacao", "hp":"Mega", "speed":"Parada", "damage":"Rajada rapida", "desc":"Mega torre de alcance global que dispara mini bolinhas rapidamente."},
    {"name":"ARCEBISPOS DOS PECADOS", "type":"Boss especial", "hp":"Alto", "speed":"Variavel", "damage":"Assinatura reduzida do Pecado", "desc":"V14: comecam na onda 35 e aparecem 5 ondas antes de cada Pecado verdadeiro."},
    {"name":"IRA", "type":"Pecado", "hp":"Extremo", "speed":"Alta", "damage":"Rajadas de furia", "desc":"Fica mais opressivo ferido e cobre a arena com rajadas vermelhas."},
    {"name":"ORGULHO", "type":"Pecado", "hp":"Extremo", "speed":"Media", "damage":"Defesa soberana", "desc":"Ativa uma guarda dourada que reduz drasticamente o dano recebido."},
    {"name":"INVEJA", "type":"Pecado", "hp":"Extremo", "speed":"Copia o jogador", "damage":"Copias em leque", "desc":"Imita a velocidade do jogador e responde com disparos verdes."},
    {"name":"GANANCIA", "type":"Pecado", "hp":"Extremo", "speed":"Media", "damage":"Roubo", "desc":"Rouba moedas da run quando chega perto e converte o roubo em cura."},
    {"name":"GULA", "type":"Pecado", "hp":"Extremo + memoria", "speed":"Alta", "damage":"Devorar", "desc":"Primeiro encontro na wave 80. Um contato real pode devorar a run e fortalece reencontros futuros."},
    {"name":"PREGUICA", "type":"Pecado", "hp":"Extremo", "speed":"Baixa", "damage":"Aura de lentidao", "desc":"Sua presenca pesa sobre o jogador e reduz drasticamente a movimentacao perto dela."},
    {"name":"LUXURIA", "type":"Pecado", "hp":"Extremo", "speed":"Imprevisivel", "damage":"Ilusoes violetas", "desc":"Teleporta pela arena e cria leques de projeteis rosa. A mecanica e puramente de combate."},
]

# ============================================================
# V13 - FORJA / MATERIAIS / ARMAS
# Materiais sao progresso persistente e NAO caem em runs de personagens Beta.
# ============================================================
FORGE_RARITIES = {
    "common": ("COMUM", (175,180,190)),
    "uncommon": ("INCOMUM", GREEN),
    "rare": ("RARO", BLUE),
    "epic": ("EPICO", PURPLE),
    "legendary": ("LENDARIO", ORANGE),
    "mythic": ("MITICO", PINK),
    "divine": ("DIVINA", DIVINE_BLUE),
}
SIN_FRAGMENTS = {
    "sin_wrath": "IRA",
    "sin_pride": "ORGULHO",
    "sin_envy": "INVEJA",
    "sin_greed": "GANANCIA",
    "sin_gula": "GULA",
    "sin_sloth": "PREGUICA",
    "sin_lust": "LUXURIA",
}
DIVINE_COST = {key: 1 for key in SIN_FRAGMENTS}
FORGE_MATERIALS = {
    "scrap": {"name":"SUCATA IRRELEVANTE", "rarity":"common", "desc":"Restos basicos de metal e equipamento sem valor aparente."},
    "essence": {"name":"ESSENCIA DO VOID", "rarity":"uncommon", "desc":"Energia condensada do Vazio, usada para alimentar efeitos especiais."},
    "core": {"name":"NUCLEO DE JESTER'S", "rarity":"rare", "desc":"Nucleo instavel encontrado em elites e inimigos poderosos."},
    "domain_crystal": {"name":"CRISTAL DE DOMINIO", "rarity":"epic", "desc":"Cristal que reage a Expansoes e habilidades especiais."},
    "boss_heart": {"name":"CORACAO DO REI", "rarity":"legendary", "desc":"Coracao condensado de bosses fortes, usado em armas de alto nivel."},
    **{key: {"name":f"PEDACO DO PECADO: {name}", "rarity":"divine", "desc":f"Fragmento divino obtido ao derrotar o Pecado da {name}."} for key,name in SIN_FRAGMENTS.items()},
}
FORGE_CHARACTER_ORDER = ["Ana", "Kevyn", "Ycaro", "Kayk", "Pedro", "Ruan", "Vasco", LIRA_KEY, "Colosso do Caos", "Glonk", "Sans", "Strikada Egoísta", "Glonk 100% Power", "Potential Man"]
FORGE_WEAPONS = [
    # KEVYN
    {"key":"kevyn_counterblade","character":"Kevyn","name":"LAMINA DO CONTRA-GOLPE","rarity":"legendary","coins":1800,
     "cost":{"scrap":24,"core":8,"domain_crystal":4,"boss_heart":2},"desc":"+45% alcance. Golpes de espada rebatem projeteis inimigos proximos."},
    {"key":"kevyn_void_edge","character":"Kevyn","name":"FIO DO VOID","rarity":"rare","coins":800,
     "cost":{"scrap":14,"essence":6,"core":2},"desc":"+20% alcance da espada e +12% dano.","mods":{"damage":1.12,"kevyn_range":1.20}},
    {"key":"kevyn_king_saber","character":"Kevyn","name":"SABRE DO REI","rarity":"epic","coins":1250,
     "cost":{"scrap":18,"core":5,"boss_heart":1},"desc":"+18% dano, +8% velocidade e começa a run com 1 escudo.","mods":{"damage":1.18,"speed":1.08,"shield":1}},
    {"key":"kevyn_jester_splitter","character":"Kevyn","name":"CORTADOR DE JESTER'S","rarity":"mythic","coins":2450,
     "cost":{"core":12,"domain_crystal":5,"boss_heart":3},"desc":"+28% dano, +35% alcance e +8% critico.","mods":{"damage":1.28,"kevyn_range":1.35,"crit":0.08}},

    # ANA
    {"key":"ana_reflex_staff","character":"Ana","name":"CAJADO DO REFLEXO","rarity":"epic","coins":1350,
     "cost":{"scrap":16,"essence":14,"core":5,"domain_crystal":3},"desc":"Ao sofrer dano, invoca uma Mini-Ana automaticamente. Cooldown: 5s."},
    {"key":"ana_void_staff","character":"Ana","name":"CAJADO DO VOID","rarity":"rare","coins":850,
     "cost":{"scrap":12,"essence":10,"core":2},"desc":"Mini-Anas ficam 30% mais rapidas e explodem numa area 15% maior.","mods":{"ana_miniana_speed":1.30,"ana_blast":1.15}},
    {"key":"ana_triune_staff","character":"Ana","name":"CAJADO TRIUNO","rarity":"legendary","coins":1750,
     "cost":{"essence":18,"core":7,"domain_crystal":4,"boss_heart":1},"desc":"Favorece invocacoes triplas e concede +30 Estamina.","mods":{"ana_three_bias":0.45,"stamina":30}},
    {"key":"ana_queen_scepter","character":"Ana","name":"CETRO DA RAINHA","rarity":"mythic","coins":2500,
     "cost":{"essence":22,"domain_crystal":7,"boss_heart":3},"desc":"+25% dano das invocacoes, +20% raio e +12% regeneracao.","mods":{"damage":1.25,"ana_blast":1.20,"regen":1.12}},

    # YCARO
    {"key":"ycaro_golden_hunter","character":"Ycaro","name":"CACADORA DOURADA","rarity":"epic","coins":1250,
     "cost":{"scrap":18,"essence":10,"core":5,"domain_crystal":2},"desc":"Shotgun ganha +2 pellets e +1 perfuracao permanente durante a run."},
    {"key":"ycaro_long_barrel","character":"Ycaro","name":"CANO DO VOID","rarity":"rare","coins":780,
     "cost":{"scrap":14,"essence":7,"core":2},"desc":"+15% dano e +1 perfuracao.","mods":{"damage":1.15,"pierce":1}},
    {"key":"ycaro_jester_chamber","character":"Ycaro","name":"CAMARA DE JESTER'S","rarity":"legendary","coins":1650,
     "cost":{"scrap":20,"core":8,"domain_crystal":3,"boss_heart":1},"desc":"+3 pellets, +6% critico e +15 Estamina.","mods":{"ycaro_pellets":3,"crit":0.06,"stamina":15}},
    {"key":"ycaro_king_shotgun","character":"Ycaro","name":"ESCOPETA DO REI","rarity":"mythic","coins":2400,
     "cost":{"core":10,"domain_crystal":5,"boss_heart":3},"desc":"+30% dano, +2 pellets e +2 perfuracao.","mods":{"damage":1.30,"ycaro_pellets":2,"pierce":2}},

    # KAYK
    {"key":"kayk_grave_pistols","character":"Kayk","name":"PISTOLAS DO TUMULO FRIO","rarity":"legendary","coins":1650,
     "cost":{"scrap":18,"essence":10,"core":8,"boss_heart":2},"desc":"Tiros explodem em area e deixam os alvos lentos por alguns segundos."},
    {"key":"kayk_jester_revolvers","character":"Kayk","name":"REVOLVERES DE JESTER'S","rarity":"rare","coins":820,
     "cost":{"scrap":14,"core":4,"essence":5},"desc":"+12% dano e +1 perfuracao nos tiros.","mods":{"damage":1.12,"pierce":1}},
    {"key":"kayk_void_twins","character":"Kayk","name":"GEMEAS DO VOID","rarity":"epic","coins":1350,
     "cost":{"essence":14,"core":6,"domain_crystal":2},"desc":"Dispara +1 par de balas e concede +20 Estamina.","mods":{"kayk_pairs":1,"stamina":20}},
    {"key":"kayk_king_barrels","character":"Kayk","name":"CANOS DO REI","rarity":"mythic","coins":2450,
     "cost":{"core":11,"domain_crystal":5,"boss_heart":3},"desc":"+25% dano, +1 par e +7% critico.","mods":{"damage":1.25,"kayk_pairs":1,"crit":0.07}},

    # PEDRO
    {"key":"pedro_king_pineapple","character":"Pedro","name":"ABACAXI DO REI","rarity":"rare","coins":900,
     "cost":{"scrap":14,"essence":8,"core":3},"desc":"Abacaxis ficam 50% maiores e 35% mais rapidos."},
    {"key":"pedro_void_fruit","character":"Pedro","name":"FRUTA DO VOID","rarity":"uncommon","coins":620,
     "cost":{"scrap":10,"essence":7},"desc":"+20% velocidade e +15% alcance dos abacaxis.","mods":{"pedro_speed":1.20,"pedro_range":1.15}},
    {"key":"pedro_jester_crown","character":"Pedro","name":"COROA DE JESTER'S","rarity":"epic","coins":1380,
     "cost":{"scrap":16,"core":6,"domain_crystal":2},"desc":"+20% dano e lança +1 abacaxi por ataque.","mods":{"damage":1.20,"pedro_extra":1}},
    {"key":"pedro_sin_harvest","character":"Pedro","name":"COLHEITA DO PECADO","rarity":"mythic","coins":2500,
     "cost":{"essence":18,"core":10,"boss_heart":3},"desc":"+30% dano, +35% velocidade e +1 abacaxi adicional.","mods":{"damage":1.30,"pedro_speed":1.35,"pedro_extra":1}},

    # RUAN
    {"key":"ruan_hell_pact","character":"Ruan","name":"PACTO DA MATILHA INFERNAL","rarity":"legendary","coins":1900,
     "cost":{"scrap":20,"core":9,"domain_crystal":4,"boss_heart":2},"desc":"Investidas deixam fogo. Amigos copiam aparencia e atributos do inimigo derrotado."},
    {"key":"ruan_jester_boots","character":"Ruan","name":"BOTAS DE JESTER'S","rarity":"rare","coins":790,
     "cost":{"scrap":14,"core":4},"desc":"+20% dano de investida e +8% velocidade.","mods":{"ruan_dash":1.20,"speed":1.08}},
    {"key":"ruan_king_pact","character":"Ruan","name":"PACTO DO REI","rarity":"epic","coins":1450,
     "cost":{"essence":12,"core":7,"boss_heart":1},"desc":"Amigos ganham +30% HP e +25% dano.","mods":{"ruan_friend_hp":1.30,"ruan_friend_damage":1.25}},
    {"key":"ruan_void_ashes","character":"Ruan","name":"CINZAS DO VOID","rarity":"mythic","coins":2450,
     "cost":{"core":10,"domain_crystal":5,"boss_heart":3},"desc":"+25% dano de investida; Amigos +20% dano e velocidade.","mods":{"ruan_dash":1.25,"ruan_friend_damage":1.20,"ruan_friend_speed":1.20}},

    # COLOSSO DO CAOS
    {"key":"father_sentence_fist","character":"Colosso do Caos","name":"PUNHO DA SENTENCA","rarity":"mythic","coins":2600,
     "cost":{"scrap":28,"core":12,"domain_crystal":6,"boss_heart":4},"desc":"Golpe em area fica 25% maior, causa +20% dano e apaga projeteis inimigos."},
    {"key":"father_scrap_glove","character":"Colosso do Caos","name":"LUVA IRRELEVANTE","rarity":"rare","coins":850,
     "cost":{"scrap":20,"essence":4},"desc":"+18% raio do golpe e +10% dano.","mods":{"father_radius":1.18,"damage":1.10}},
    {"key":"father_king_seal","character":"Colosso do Caos","name":"SELO DO REI","rarity":"legendary","coins":1800,
     "cost":{"core":8,"domain_crystal":4,"boss_heart":2},"desc":"+25% dano contra bosses, +20 HP e +1 escudo.","mods":{"father_boss":1.25,"hp":20,"shield":1}},
    {"key":"father_void_hand","character":"Colosso do Caos","name":"MAO DO VOID","rarity":"mythic","coins":2700,
     "cost":{"essence":18,"core":12,"domain_crystal":7,"boss_heart":3},"desc":"+25% raio do golpe, +20% raio do Dominio e +20% dano.","mods":{"father_radius":1.25,"father_domain":1.20,"damage":1.20}},

    # DIVINAS - o custo e sempre 1 fragmento de cada um dos sete Pecados.
    {"key":"kevyn_seven_faces","character":"Kevyn","name":"LAMINA CELESTIAL DAS SETE FACES","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"desc":"Cortes a distancia. Segurar DASH 1s ativa a atracao azul; toque curto continua sendo Dash normal. Segurar ATK repete os cortes; PARRY 1s repele; DOM 3s libera uma explosao roxa absoluta."},
    {"key":"ana_longinus","character":"Ana","name":"LANCA DE LONGINUS","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"desc":"Segure ATK 2s para criar a primeira Mini-Ana orbital. Mantendo pressionado, cada +3s cria outra. Cada orbital elimina o primeiro alvo que tocar e desaparece."},
    {"key":"kayk_big_builder","character":"Kayk","name":"BIG BUILDER","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"desc":"Segurar DASH 1s cura HP/Estamina totalmente 1x por onda. Toque curto continua sendo Dash normal. +1 bala frontal e 3 tiros curtos para tras/lados."},
    {"key":"ycaro_shotgun_shelly","character":"Ycaro","name":"SHOTGUN-SHELLY","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"desc":"Disparos nao gastam Estamina, cooldown pela metade e cada tiro concede um impulso de velocidade."},
    {"key":"ruan_monarch_cloak","character":"Ruan","name":"MANTO DO MONARCA","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"desc":"Se nao houver nenhum Amigo normal vivo, um DASH invoca 1 Amigo no ponto de partida. Segurar DASH 1s teleporta o dobro da distancia. Amigos herdam propriedades do inimigo recrutado (ex.: atiradores tambem disparam) e podem soltar orbes de +5 HP."},
    {"key":"pedro_hunting_time","character":"Pedro","name":"TEMPO DE CACA","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"desc":"+100% velocidade. Abacaxis sao teleguiados e sempre recuperam HP/Estamina. Segurar DASH 1s planta um abacaxi que fere inimigos e cura 10 HP ao ser recolhido."},
    {"key":"vasco_dharma_helm","character":"Vasco","name":"LEME DE DHARMA","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"preview":True,"testable":True,
     "desc":"[BETA TESTAVEL] Wave perfeita gira o Leme: -5% dano recebido por adaptacao, acumulando ate -70%. Jackpot nao conta como adaptacao."},

    # PREVIAS DIVINAS - Sans/Sukuna estao em Beta; Strikada/Glonk 100%/Potential sao personagens normais,
    # mas algumas Divinas ainda ficam como previa ate receberem integracao propria.
    {"key":"sans_final_judgement","character":"Sans","name":"JULGAMENTO DO ULTIMO ATALHO","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA BETA] Blasters atravessam a arena em cadeia e ossos ganham trajetorias impossiveis. Integracao reservada para a saida do Beta."},
    {"key":"strikada_absolute_ego","character":"Strikada Egoísta","name":"EGO ABSOLUTO: GOL IMPOSSIVEL","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA] A bola reconhece todos os alvos da arena e transforma cada quique em uma nova rota de gol."},
    {"key":"glonk_over_100","character":"Glonk 100% Power","name":"101% POWER","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA] Um equipamento absurdo para o ser de 1 HP e 1 de dano. Efeito final ainda esta em desenvolvimento."},
    {"key":"potential_totality","character":"Potential Man","name":"DEZ SOMBRAS: TOTALIDADE","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA] Cães, sapos e Mahoraga compartilham uma invocacao total. Integracao final ainda esta em desenvolvimento."},

    # GLONK - equipamentos nao fazem ele atacar; apenas adiam o inevitavel.
    {"key":"glonk_irrelevant_rock","character":"Glonk","name":"PEDRA IRRELEVANTE","rarity":"common","coins":250,
     "cost":{"scrap":8},"desc":"Glonk continua sem fazer nada, mas demora cerca de 25% mais para cumprir seu destino.","mods":{"glonk_decay":0.80}},
    {"key":"glonk_void_hat","character":"Glonk","name":"CHAPEU DO VOID","rarity":"epic","coins":1000,
     "cost":{"scrap":12,"essence":12,"domain_crystal":2},"desc":"Reduz a velocidade da autodestruicao de Glonk em 45%.","mods":{"glonk_decay":0.55}},
    {"key":"glonk_king_crown","character":"Glonk","name":"COROA DO REI GLONK","rarity":"mythic","coins":2200,
     "cost":{"core":8,"boss_heart":2,"sin_gula":1},"desc":"Glonk dura quase o dobro do tempo. Ainda nao anda, ataca ou possui Dominio.","mods":{"glonk_decay":0.52}},
]
FORGE_WEAPON_BY_KEY = {w["key"]: w for w in FORGE_WEAPONS}


PERMANENT_UPGRADES = [
    ("vitality_level", "VITALIDADE", "+8 HP e +6 Estamina por nivel", 45),
    ("damage_level", "DANO BRUTO", "+8% dano inicial por nivel", 55),
    ("speed_level", "PASSOS RAPIDOS", "+3% velocidade por nivel", 40),
    ("stamina_level", "RESERVA EXTRA", "+10 Estamina maxima por nivel", 50),
    ("regen_level", "PULMAO TREINADO", "+6% regeneracao de Estamina por nivel", 60),
    ("armor_level", "PELE DE FERRO", "-3% dano recebido por nivel (ate 45%)", 70),
    ("healing_level", "CURA EFICIENTE", "+4% cura recebida por nivel", 65),
    ("domain_level", "RITUAL ACELERADO", "+6% carga de Dominio recebida por nivel", 80),
    ("orb_level", "IMA DE ORBES", "+2% chance de drops por nivel", 55),
    ("coin_level", "GANANCIA SAUDAVEL", "+5% moedas obtidas por nivel", 75),
    ("dash_level", "IMPULSO", "-4% cooldown do Dash por nivel (ate 40%)", 70),
    ("crit_level", "MIRA NERVOSA", "+2% chance critica inicial por nivel (ate 20%)", 85),
]
PERMANENT_UPGRADE_CAP = 30

ACHIEVEMENTS = [
    ('kill_50', 'PRIMEIROS PASSOS', 'Derrote 50 inimigos no total.'),
    ('kill_100', 'PRIMEIRO MASSACRE', 'Derrote 100 inimigos no total.'),
    ('kill_250', 'A ARENA LEMBROU', 'Derrote 250 inimigos no total.'),
    ('kill_500', 'SEM DESCANSO', 'Derrote 500 inimigos no total.'),
    ('kill_1000', 'AQUECIMENTO ACABOU', 'Derrote 1.000 inimigos no total.'),
    ('kill_2500', 'CONTAGEM ABSURDA', 'Derrote 2.500 inimigos no total.'),
    ('kill_5000', 'NAO ACABA NUNCA', 'Derrote 5.000 inimigos no total.'),
    ('kill_7500', 'SETE MIL E QUINHENTOS', 'Derrote 7.500 inimigos no total.'),
    ('kill_10000', 'GENOCIDA DE PIXELS', 'Derrote 10.000 inimigos no total.'),
    ('kill_15000', 'QUINZE MIL', 'Derrote 15.000 inimigos no total.'),
    ('kill_25000', 'EXERCITO INTEIRO', 'Derrote 25.000 inimigos no total.'),
    ('kill_40000', 'QUARENTA MIL', 'Derrote 40.000 inimigos no total.'),
    ('kill_60000', 'MAQUINA DE KOs', 'Derrote 60.000 inimigos no total.'),
    ('kill_80000', 'OITENTA MIL', 'Derrote 80.000 inimigos no total.'),
    ('kill_100000', 'CEM MIL MOTIVOS', 'Derrote 100.000 inimigos no total.'),
    ('wave_5', 'PRIMEIRO AQUECIMENTO', 'Alcance a onda 5.'),
    ('wave_10', 'DEZ ONDAS', 'Alcance a onda 10.'),
    ('wave_20', 'VINTE ONDAS', 'Alcance a onda 20.'),
    ('wave_30', 'TRINTA SEM PARAR', 'Alcance a onda 30.'),
    ('wave_35', 'O PRIMEIRO PRESSAGIO', 'Alcance a onda 35 e encare o primeiro Arcebispo.'),
    ('wave_40', 'IRA NA PORTA', 'Alcance a onda 40.'),
    ('wave_50', 'METADE DO INFERNO', 'Alcance a onda 50.'),
    ('wave_60', 'SESSENTA', 'Alcance a onda 60.'),
    ('wave_70', 'SETENTA', 'Alcance a onda 70.'),
    ('wave_80', 'OITENTA', 'Alcance a onda 80.'),
    ('wave_90', 'NOVENTA', 'Alcance a onda 90.'),
    ('wave_95', 'ULTIMO ARCEBISPO', 'Alcance a onda 95.'),
    ('wave_99', 'NA PORTA DO FIM', 'Alcance a onda 99.'),
    ('wave_100', 'CEM ONDAS', 'Alcance a onda 100.'),
    ('solo_survivor', 'SOBROU SO EU', 'Conclua o modo UM CONTRA TODOS.'),
    ('domain_10', 'RITUAL INICIANTE', 'Ative 10 Dominios no total.'),
    ('domain_25', 'VINTE E CINCO RITUAIS', 'Ative 25 Dominios no total.'),
    ('domain_50', 'CINQUENTA PORTAS', 'Ative 50 Dominios no total.'),
    ('domain_100', 'RITUAL APRENDIZ', 'Ative 100 Dominios no total.'),
    ('domain_150', 'DOMINIO RECORRENTE', 'Ative 150 Dominios no total.'),
    ('domain_250', 'DUZENTOS E CINQUENTA', 'Ative 250 Dominios no total.'),
    ('domain_500', 'RITUALISTA', 'Ative 500 Dominios no total.'),
    ('domain_750', 'SETECENTOS E CINQUENTA', 'Ative 750 Dominios no total.'),
    ('domain_1000', 'MIL DOMINIOS', 'Ative 1.000 Dominios no total.'),
    ('domain_1500', 'MIL E QUINHENTOS', 'Ative 1.500 Dominios no total.'),
    ('clash_1', 'PRIMEIRO CLASH', 'Venca 1 Clash de Dominio no total.'),
    ('clash_3', 'TRES CLASHES', 'Venca 3 Clashes de Dominio no total.'),
    ('clash_5', 'CINCO CLASHES', 'Venca 5 Clashes de Dominio no total.'),
    ('clash_10', 'IMPERADOR DOS DOMINIOS', 'Venca 10 Clashes de Dominio no total.'),
    ('clash_20', 'VINTE VITORIAS', 'Venca 20 Clashes de Dominio no total.'),
    ('clash_35', 'TRINTA E CINCO', 'Venca 35 Clashes de Dominio no total.'),
    ('clash_50', 'CINQUENTA CLASHES', 'Venca 50 Clashes de Dominio no total.'),
    ('clash_100', 'CEM VEZES SOBERANO', 'Venca 100 Clashes de Dominio no total.'),
    ('forge_first', 'FERREIRO DE QUINTAL', 'Fabrique 1 arma diferente na Forja.'),
    ('forge_3', 'ARSENAL PEQUENO', 'Fabrique 3 armas diferentes na Forja.'),
    ('forge_5', 'COLECIONADOR DE FERRO', 'Fabrique 5 armas diferentes na Forja.'),
    ('forge_10', 'DEZ RECEITAS', 'Fabrique 10 armas diferentes na Forja.'),
    ('forge_15', 'MESTRE DA FORJA', 'Fabrique 15 armas diferentes na Forja.'),
    ('forge_20', 'VINTE ARMAS', 'Fabrique 20 armas diferentes na Forja.'),
    ('forge_25', 'ARSENAL PESADO', 'Fabrique 25 armas diferentes na Forja.'),
    ('forge_30', 'TRINTA CRIACOES', 'Fabrique 30 armas diferentes na Forja.'),
    ('missions_1', 'PRIMEIRO CONTRATO', 'Conclua 1 missao de personagem.'),
    ('missions_3', 'TRES CONTRATOS', 'Conclua 3 missaooes de personagem.'),
    ('missions_5', 'CINCO CONTRATOS', 'Conclua 5 missaooes de personagem.'),
    ('missions_10', 'DEZ MISSOES', 'Conclua 10 missaooes de personagem.'),
    ('missions_15', 'QUINZE MISSOES', 'Conclua 15 missaooes de personagem.'),
    ('missions_20', 'VINTE MISSOES', 'Conclua 20 missaooes de personagem.'),
    ('missions_25', 'VINTE E CINCO', 'Conclua 25 missaooes de personagem.'),
    ('missions_30', 'TRINTA MISSOES', 'Conclua 30 missaooes de personagem.'),
    ('evo_1', 'PRIMEIRO PONTO', 'Distribua 1 ponto de Evolucao entre personagens normais.'),
    ('evo_5', 'CINCO PASSOS', 'Distribua 5 pontos de Evolucao entre personagens normais.'),
    ('evo_10', 'DEZ MELHORIAS', 'Distribua 10 pontos de Evolucao entre personagens normais.'),
    ('evo_25', 'VINTE E CINCO PONTOS', 'Distribua 25 pontos de Evolucao entre personagens normais.'),
    ('evo_50', 'CINQUENTA PONTOS', 'Distribua 50 pontos de Evolucao entre personagens normais.'),
    ('evo_100', 'CEM PONTOS', 'Distribua 100 pontos de Evolucao entre personagens normais.'),
    ('evo_150', 'CENTO E CINQUENTA', 'Distribua 150 pontos de Evolucao entre personagens normais.'),
    ('evo_200', 'DUZENTOS PONTOS', 'Distribua 200 pontos de Evolucao entre personagens normais.'),
    ('sin_wrath_defeated', 'A IRA ESFRIOU', 'Derrote o Pecado da Ira.'),
    ('sin_pride_defeated', 'ORGULHO QUEBRADO', 'Derrote o Pecado da Orgulho.'),
    ('sin_envy_defeated', 'NADA A INVEJAR', 'Derrote o Pecado da Inveja.'),
    ('sin_greed_defeated', 'NAO DA PRA COMPRAR ISSO', 'Derrote o Pecado da Ganancia.'),
    ('gula_defeated', 'A FOME PASSOU', 'Derrote o Pecado da Gula.'),
    ('sin_sloth_defeated', 'LEVANTA DAI', 'Derrote o Pecado da Preguica.'),
    ('sin_lust_defeated', 'DESEJO NEGADO', 'Derrote o Pecado da Luxuria.'),
    ('all_sins', 'OS SETE CAIRAM', 'Derrote os sete Pecados pelo menos uma vez.'),
    ('fragment_wrath', 'PEDACO: IRA', 'Possua ao menos 1 Pedaco do Pecado: IRA.'),
    ('fragment_pride', 'PEDACO: ORGULHO', 'Possua ao menos 1 Pedaco do Pecado: ORGULHO.'),
    ('fragment_envy', 'PEDACO: INVEJA', 'Possua ao menos 1 Pedaco do Pecado: INVEJA.'),
    ('fragment_greed', 'PEDACO: GANANCIA', 'Possua ao menos 1 Pedaco do Pecado: GANANCIA.'),
    ('fragment_gula', 'PEDACO: GULA', 'Possua ao menos 1 Pedaco do Pecado: GULA.'),
    ('fragment_sloth', 'PEDACO: PREGUICA', 'Possua ao menos 1 Pedaco do Pecado: PREGUICA.'),
    ('fragment_lust', 'PEDACO: LUXURIA', 'Possua ao menos 1 Pedaco do Pecado: LUXURIA.'),
    ('all_sin_fragments', 'COLECAO PROIBIDA', 'Tenha ao menos 1 Pedaco de cada Pecado ao mesmo tempo.'),
    ('parry_100', 'MESTRE DO PARRY', 'Faca 100 Parries na mesma run.'),
    ('dodge_75', 'INTOCAVEL', 'Faca 75 Perfect Dodges na mesma run.'),
    ('combo_50', 'SEM DEIXAR RESPIRAR', 'Alcance o combo maximo x50.'),
    ('pineapple_25', 'ABACAXI ECONOMICO', 'Recupere HP/STA 25 vezes com abacaxis.'),
    ('friend_12', 'PODER DA AMIZADE', 'Tenha 12 amigos do Ruan vivos ao mesmo tempo.'),
    ('father_unlock', 'O CAOS DESPERTO', 'Desbloqueie o Colosso do Caos.'),
    ('divine_weapon', 'TOQUE DIVINO', 'Fabrique sua primeira arma de raridade Divina.'),
    ('level_10', 'NIVEL DEZ', 'Tenha qualquer personagem normal no nivel 10 ou superior.'),
    ('level_25', 'NIVEL VINTE E CINCO', 'Tenha qualquer personagem normal no nivel 25 ou superior.'),
    ('level_50', 'NIVEL CINQUENTA', 'Tenha qualquer personagem normal no nivel 50 ou superior.'),
    ('level_100', 'NIVEL CEM', 'Tenha qualquer personagem normal no nivel 100 ou superior.'),
    ('meta_all', 'Não é difícil, só e chato', 'Desbloqueie TODAS as outras 99 conquistas.'),
]

ACHIEVEMENT_PROGRESS_RULES = {
    'kill_50': ('kills', 50),
    'kill_100': ('kills', 100),
    'kill_250': ('kills', 250),
    'kill_500': ('kills', 500),
    'kill_1000': ('kills', 1000),
    'kill_2500': ('kills', 2500),
    'kill_5000': ('kills', 5000),
    'kill_7500': ('kills', 7500),
    'kill_10000': ('kills', 10000),
    'kill_15000': ('kills', 15000),
    'kill_25000': ('kills', 25000),
    'kill_40000': ('kills', 40000),
    'kill_60000': ('kills', 60000),
    'kill_80000': ('kills', 80000),
    'kill_100000': ('kills', 100000),
    
    'wave_5': ('wave', 5),
    'wave_10': ('wave', 10),
    'wave_20': ('wave', 20),
    'wave_30': ('wave', 30),
    'wave_35': ('wave', 35),
    'wave_40': ('wave', 40),
    'wave_50': ('wave', 50),
    'wave_60': ('wave', 60),
    'wave_70': ('wave', 70),
    'wave_80': ('wave', 80),
    'wave_90': ('wave', 90),
    'wave_95': ('wave', 95),
    'wave_99': ('wave', 99),
    'wave_100': ('wave', 100),
    'domain_10': ('domains', 10),
    'domain_25': ('domains', 25),
    'domain_50': ('domains', 50),
    'domain_100': ('domains', 100),
    'domain_150': ('domains', 150),
    'domain_250': ('domains', 250),
    'domain_500': ('domains', 500),
    'domain_750': ('domains', 750),
    'domain_1000': ('domains', 1000),
    'domain_1500': ('domains', 1500),
    'clash_1': ('clashes', 1),
    'clash_3': ('clashes', 3),
    'clash_5': ('clashes', 5),
    'clash_10': ('clashes', 10),
    'clash_20': ('clashes', 20),
    'clash_35': ('clashes', 35),
    'clash_50': ('clashes', 50),
    'clash_100': ('clashes', 100),
    'forge_first': ('crafted', 1),
    'forge_3': ('crafted', 3),
    'forge_5': ('crafted', 5),
    'forge_10': ('crafted', 10),
    'forge_15': ('crafted', 15),
    'forge_20': ('crafted', 20),
    'forge_25': ('crafted', 25),
    'forge_30': ('crafted', 30),
    'missions_1': ('missions', 1),
    'missions_3': ('missions', 3),
    'missions_5': ('missions', 5),
    'missions_10': ('missions', 10),
    'missions_15': ('missions', 15),
    'missions_20': ('missions', 20),
    'missions_25': ('missions', 25),
    'missions_30': ('missions', 30),
    'evo_1': ('evo_spent', 1),
    'evo_5': ('evo_spent', 5),
    'evo_10': ('evo_spent', 10),
    'evo_25': ('evo_spent', 25),
    'evo_50': ('evo_spent', 50),
    'evo_100': ('evo_spent', 100),
    'evo_150': ('evo_spent', 150),
    'evo_200': ('evo_spent', 200),
    'sin_wrath_defeated': ('sin_defeat:wrath', 1),
    'sin_pride_defeated': ('sin_defeat:pride', 1),
    'sin_envy_defeated': ('sin_defeat:envy', 1),
    'sin_greed_defeated': ('sin_defeat:greed', 1),
    'gula_defeated': ('sin_defeat:gula', 1),
    'sin_sloth_defeated': ('sin_defeat:sloth', 1),
    'sin_lust_defeated': ('sin_defeat:lust', 1),
    'all_sins': ('sins_defeated', 7),
    'fragment_wrath': ('fragment:sin_wrath', 1),
    'fragment_pride': ('fragment:sin_pride', 1),
    'fragment_envy': ('fragment:sin_envy', 1),
    'fragment_greed': ('fragment:sin_greed', 1),
    'fragment_gula': ('fragment:sin_gula', 1),
    'fragment_sloth': ('fragment:sin_sloth', 1),
    'fragment_lust': ('fragment:sin_lust', 1),
    'all_sin_fragments': ('fragments_all', 7),
    'parry_100': ('run_parries', 100),
    'dodge_75': ('run_dodges', 75),
    'combo_50': ('run_combo', 50),
    'pineapple_25': ('pineapple_refunds', 25),
    'friend_12': ('run_friends', 12),
    'father_unlock': ('father_unlock', 1),
    'divine_weapon': ('divine_weapon', 1),
    'level_10': ('max_level', 10),
    'level_25': ('max_level', 25),
    'level_50': ('max_level', 50),
    'level_100': ('max_level', 100),
}
ACHIEVEMENT_RARITY_COLORS = {
    "common": WHITE,
    "uncommon": GREEN,
    "rare": BLUE,
    "epic": PURPLE,
    "legendary": YELLOW,
    "divine": DIVINE_BLUE,
    "meta": META_ACH_COLOR,
}
ACHIEVEMENT_RARITY_NAMES = {
    "common":"COMUM", "uncommon":"INCOMUM", "rare":"RARA", "epic":"EPICA",
    "legendary":"LENDARIA", "divine":"DIVINA", "meta":"FINAL",
}

def achievement_rarity(key):
    if key == "meta_all": return "meta"
    if key in ("wave_100","all_sins","all_sin_fragments","divine_weapon","level_100","solo_survivor"):
        return "divine"
    if key.startswith("sin_") or key in ("gula_defeated","father_unlock"):
        return "legendary"
    if key.startswith("fragment_"):
        return "epic"
    rule = ACHIEVEMENT_PROGRESS_RULES.get(key)
    if not rule: return "rare"
    metric, goal = rule
    if metric == "wave":
        if goal >= 95: return "divine"
        if goal >= 80: return "legendary"
        if goal >= 50: return "epic"
        if goal >= 35: return "rare"
        if goal >= 20: return "uncommon"
        return "common"
    if metric == "kills":
        if goal >= 80000: return "divine"
        if goal >= 25000: return "legendary"
        if goal >= 7500: return "epic"
        if goal >= 1000: return "rare"
        if goal >= 250: return "uncommon"
        return "common"
    if metric in ("domains","clashes","crafted","missions","evo_spent","max_level"):
        ratio = goal
        limits = {
            "domains": (25,100,500,1000), "clashes": (3,10,35,100), "crafted": (3,10,20,30),
            "missions": (3,10,20,30), "evo_spent": (10,50,150,200), "max_level": (10,25,50,100),
        }.get(metric,(5,20,50,100))
        if ratio >= limits[3]: return "divine"
        if ratio >= limits[2]: return "legendary"
        if ratio >= limits[1]: return "epic"
        if ratio >= limits[0]: return "rare"
        return "uncommon"
    return "rare"


CHARACTER_MISSIONS = {
    "Ana": [
        ("ana_kills_v12", "REALIDADE HOSTIL", "Derrote 1.500 inimigos com Ana", "kills", 1500, 1800),
        ("ana_domains_v12", "SEM SAIDA", "Ative 120 Dominios com Ana", "domains", 120, 2200),
        ("ana_wave_v12", "ANOMALIA ESTAVEL", "Alcance a onda 180 com Ana", "best_wave", 180, 3500),
    ],
    "Kevyn": [
        ("kevyn_kills_v12", "LAMINA PACIENTE", "Derrote 2.000 inimigos com Kevyn", "kills", 2000, 2000),
        ("kevyn_domains_v12", "FORA DO TEMPO", "Ative 150 Dominios com Kevyn", "domains", 150, 2500),
        ("kevyn_wave_v12", "MURALHA VIVA", "Alcance a onda 220 com Kevyn", "best_wave", 220, 4000),
    ],
    "Ycaro": [
        ("ycaro_kills_v12", "CACA ABERTA", "Derrote 2.500 inimigos com Ycaro", "kills", 2500, 2300),
        ("ycaro_domains_v12", "CAMPO DO ZUMBI", "Ative 175 Dominios com Ycaro", "domains", 175, 2800),
        ("ycaro_wave_v12", "NAO PASSA", "Alcance a onda 260 com Ycaro", "best_wave", 260, 4500),
    ],
    "Kayk": [
        ("kayk_kills_v12", "DOIS GATILHOS", "Derrote 3.000 inimigos com Kayk", "kills", 3000, 2600),
        ("kayk_domains_v12", "NECROPOLE", "Ative 220 Dominios com Kayk", "domains", 220, 3200),
        ("kayk_wave_v12", "MIL ALMAS", "Alcance a onda 320 com Kayk", "best_wave", 320, 5200),
    ],
    "Pedro": [
        ("pedro_kills_v12", "COLHEITA", "Derrote 2.200 inimigos com Pedro", "kills", 2200, 2200),
        ("pedro_domains_v12", "X DA COLHEITA", "Ative 170 Dominios com Pedro", "domains", 170, 2700),
        ("pedro_wave_v12", "ABACAXI SUPREMO", "Alcance a onda 260 com Pedro", "best_wave", 260, 4500),
    ],
    "Ruan": [
        ("ruan_kills_v12", "RECRUTADOR", "Derrote 2.500 inimigos com Ruan", "kills", 2500, 2400),
        ("ruan_domains_v12", "REINO DOS AMIGOS", "Ative 200 Dominios com Ruan", "domains", 200, 3100),
        ("ruan_wave_v12", "AMIZADE ETERNA", "Alcance a onda 300 com Ruan", "best_wave", 300, 5000),
    ],
    "Strikada Egoísta": [
        ("strikada_kills_v13", "STRIKER EGOISTA", "Derrote 2.500 inimigos com Strikada Egoista", "kills", 2500, 2500),
        ("strikada_domains_v13", "CADEADO AZUL", "Ative 180 Dominios com Strikada Egoista", "domains", 180, 2900),
        ("strikada_wave_v13", "METAVISAO", "Alcance a onda 300 com Strikada Egoista", "best_wave", 300, 5000),
    ],
    "Glonk 100% Power": [
        ("glonk100_kills_v13", "UM DANO DE CADA VEZ", "Derrote 1.000 inimigos com Glonk 100% Power", "kills", 1000, 3000),
        ("glonk100_wave_v13", "PODER ABSOLUTO", "Alcance a onda 150 com Glonk 100% Power", "best_wave", 150, 4500),
        ("glonk100_runs_v13", "100% COMPROMETIDO", "Inicie 50 runs com Glonk 100% Power", "runs", 50, 2500),
    ],
    "Colosso do Caos": [
        ("father_kills_v12", "AUTORIDADE", "Derrote 4.000 inimigos com o Colosso do Caos", "kills", 4000, 3200),
        ("father_domains_v12", "SENTENCA", "Ative 300 Dominios com o Colosso do Caos", "domains", 300, 4000),
        ("father_wave_v12", "SENHOR DO CAOS", "Alcance a onda 400 com o Colosso do Caos", "best_wave", 400, 7000),
    ],
    "Vinicius 13": [
        ("vinicius_kills_v13", "FARM DAVIZAO", "Derrote 3.000 inimigos com Vinicius 13", "kills", 3000, 2800),
        ("vinicius_wave_v13", "ISSO QUE E AUTOMATICO", "Alcance a onda 320 com Vinicius 13", "best_wave", 320, 5200),
        ("vinicius_runs_v13", "SO MAIS UMA VEZ", "Inicie 75 runs com Vinicius 13", "runs", 75, 3000),
    ],
    "Glonk": [
        ("glonk_runs_v12", "GLONK GAMING", "Inicie 100 runs com Glonk", "runs", 100, 2500),
    ],
}


WHATS_NEW_V13 = [
    'V13: sistema de PERSONAGENS com carrossel, fichas detalhadas e Pontos de Evolucao individuais.',
    'V13: personagens em BETA ganharam uma area propria, sem progresso permanente enquanto estiverem em testes.',
    'FORJA: inimigos e bosses passaram a derrubar materiais usados com moedas para fabricar equipamentos.',
    'ITENS e ARMAS: inventario separado por materiais, Pedacos dos Pecados e arsenal filtrado por personagem.',
    'RARIDADE DIVINA: armas azul-claro exigem 1 Pedaco de cada um dos sete Pecados e liberam mecanicas especiais.',
    'PECADOS: Arcebispos e Pecados entraram no endgame e seus Pedacos passaram a alimentar a Forja Divina.',
    'VINICIUS 13: projeteis encadeados, Sucata Inimiga, mini-torres e tres Mega Torres.',
    'BESTIARIO: invocacoes foram catalogadas e o TREINAMENTO permite testar inimigos e bosses sem progresso ou loot.',
    'LOJA PERMANENTE: upgrades ganharam limite maximo de LV.30.',
    'CONQUISTAS: o jogo passou a ter 100 desafios com barra de progresso e conquista final especial.',
    'BACKUP: exportacao/restauracao de progresso e clipboard nativo Android foram adicionados.',
    'HUD: cooldowns de ataque, Dash, Parry/Blaster e habilidades especiais passaram a aparecer durante a run.',
]

WHATS_NEW_V14 = [
    'V14 FINAL: cinco dificuldades foram rebalanceadas; Facil e Normal ficaram mais acessiveis, enquanto Monarca e IMPOSSIVEL pagam melhor.',
    'V14: cada onda vencida concede 1 Ponto de Evolucao garantido para personagens com progressao.',
    'V14: o endgame foi comprimido para 100 waves; Arcebispos/Pecados aparecem muito mais cedo e a wave 100 representa o antigo fim de jogo.',
    'V14: velocidade dos inimigos foi desacoplada da compressao de waves para evitar inimigos teleportando pelo mapa.',
    'MODOS DE JOGO: Padrao, Infinito, Boss Rush, Arena, Extincao, Evolucao e modos secretos passaram a alterar as regras da partida.',
    'EXTINCAO: nenhuma fonte de HP funciona; passivas, itens, orbes, armas e regeneracoes ficam bloqueados.',
    'UM CONTRA TODOS: rivais usam versoes boss dos proprios kits, com ataques, summons, Dash, Parry e Dominios quando aplicavel.',
    'GLONK, O ULTIMO: Glonk raro pode fugir durante a wave e se transformar quando fica sozinho, com lingua, choro, birra, mini-Glonks e explosao final.',
    'DOMINIOS: a barra nao recarrega enquanto a propria Expansao esta ativa; bosses, Pecados e rivais compativeis tambem podem abrir Dominios.',
    'PERSONAGENS: Strikada Egoista e Glonk 100% Power sairam do Beta e receberam condicoes proprias de desbloqueio.',
    'V14 FINAL: Kayk, Ycaro e Pedro usam segundo analogico para mirar ataques independentemente da direcao do movimento.',
    'V14 FINAL: a primeira wave nunca e boss nos modos tradicionais e Strikada exige wave 30 no PADRAO em dificuldade NORMAL ou superior.',
    'CONQUISTAS: as 100 metas foram recalibradas para o novo teto de 100 waves e receberam raridades/cores diferentes.',
    'COMBATE: dano recebido nao concede mais imunidade automatica; somente Dash e defesas intencionais continuam protegendo.',
    'MUSICA: temas externos de menu e batalha foram integrados com loop automatico e fallback seguro.',
    'CONFIGURACOES: volumes de MUSICA e EFEITOS agora podem ser ajustados de 0 a 100 e ficam salvos.',
    'PAINEL DEV: inclui dinheiro, Pontos de Evolucao, onda inicial, imortalidade, dano infinito, itens infinitos e atalhos de maximizacao.',
]

WHATS_NEW_V15 = [
    'V15: sistema de PASSIVAS com roleta, auto-roll, configuracoes de parada e dois slots fixos por personagem.',
    'V15: Power Ups 2.0 chegaram com TAGS invisiveis, filtros de compatibilidade, upgrades gerais, sinergias e assinaturas por personagem.',
    'V15: Vasco, Lira Solis e Hank foram adicionados ao elenco principal, enquanto Sukuna, Rip_Indra e Hisoka entraram em BETA para testes.',
    'V15: Mahoraga recebeu cutscene propria, audio dedicado e tema exclusivo; Sukuna tambem ganhou Fuuga, Santuario Malevolente e Dedos do Sukuna.',
    'V15: Hank ganhou mira com pre-visualizacao do tiro, artilharia mais impactante e Dominio com canhao plantado.',
    'V15: Rip_Indra recebeu corte carregado em 3 ondas e agora o clique possui sprite/efeito proprio de ataque.',
    'V15: Ruan teve os Amigos tornados persistentes ate morrerem e o Manto do Monarca faz a tropa herdar propriedades do inimigo derrotado.',
    'V15: o menu de NOVIDADES agora possui aba propria desta versao para manter V13, V14 e V15 organizadas.',
]

WHATS_NEW_BY_VERSION = {"V13": WHATS_NEW_V13, "V14": WHATS_NEW_V14, "V15": WHATS_NEW_V15}

# ============================================================
# V15 - ROLETA GERAL DE PASSIVAS
# Duas passivas por personagem. A roleta custa 1 Ponto de Evolucao.
# Enfraquecedoras existem no catalogo, mas nao entram na roleta normal.
# ============================================================
PASSIVE_RARITIES = {
    "common":    {"name":"COMUM",          "color":(209,213,219), "border":(209,213,219), "chance":60.0},
    "rare":      {"name":"RARA",           "color":(59,130,246),  "border":(59,130,246),  "chance":20.0},
    "epic":      {"name":"EPICA",          "color":(168,85,247),  "border":(168,85,247),  "chance":10.0},
    "legendary": {"name":"LENDARIA",       "color":(245,158,11),  "border":(245,158,11),  "chance":5.0},
    "mythic":    {"name":"MITICA",         "color":(236,72,153),  "border":(236,72,153),  "chance":3.0},
    "secret":    {"name":"SECRETA",        "color":(239,68,68),   "border":(239,68,68),   "chance":1.2},
    "shiny":     {"name":"BRILHANTE",      "color":(250,204,21),  "border":(250,204,21),  "chance":0.3},
    "divine":    {"name":"DIVINA",         "color":(103,232,249), "border":(103,232,249), "chance":0.4},
    "demonic":   {"name":"DEMONIACA",      "color":(23,23,23),    "border":(185,28,28),   "chance":0.1},
    "weakening": {"name":"ENFRAQUECEDORA", "color":(107,142,35),  "border":(107,142,35),  "chance":0.0},
}

PASSIVE_ROLL_ORDER = ["common","rare","epic","legendary","mythic","secret","shiny","divine","demonic"]
PASSIVE_HIGH_EXCLUSIVE = {"secret","divine","demonic"}


def _passive(key, rarity, name, en, desc, family=None, rollable=True):
    return {"key":key,"rarity":rarity,"name":name,"en":en,"desc":desc,"family":family,"rollable":rollable}

PASSIVES = [
    # COMUNS
    _passive("strong_1","common","Potencia I","Strong I","+5% de dano em ataques e habilidades.","strong"),
    _passive("genius_1","common","Aprendizado I","Genius I","Cada upgrade: +2% dano, ate +6% na run.","genius"),
    _passive("tactical_1","common","Caca-Gigantes I","Tactical I","+8% de dano contra bosses.","tactical"),
    _passive("rich_1","common","Ganancia I","Rich I","+5% de moedas recebidas.","rich"),
    _passive("lucky_1","common","Precisao I","Lucky I","+3 pontos percentuais de critico.","precision"),
    _passive("first_friend","common","Companheiro Inicial","First Friend","+5% HP maximo e +3% dano. Passiva inicial.",rollable=False),
    # RARAS
    _passive("strong_2","rare","Potencia II","Strong II","+10% de dano.","strong"),
    _passive("genius_2","rare","Aprendizado II","Genius II","Cada upgrade: +3% dano, ate +12%.","genius"),
    _passive("rich_2","rare","Ganancia II","Rich II","+10% de moedas.","rich"),
    _passive("collector_1","rare","Catador I","Collector I","+15% de raio de coleta.","collector"),
    _passive("leader_1","rare","Lideranca I","Leader I","+4% de dano ao jogador e aliados.","leader"),
    _passive("diligent_1","rare","Persistencia I","Diligent I","Cada wave: +2% HP maximo, ate +10%; nao cura.","diligent"),
    # EPICAS
    _passive("strong_3","epic","Potencia III","Strong III","+15% de dano.","strong"),
    _passive("tactical_2","epic","Caca-Gigantes II","Tactical II","+15% de dano contra bosses.","tactical"),
    _passive("collector_2","epic","Catador II","Collector II","+30% de raio de coleta.","collector"),
    _passive("rich_3","epic","Ganancia III","Rich III","+15% de moedas.","rich"),
    _passive("speedy","epic","Impulso","Speedy","+10% movimento e +8% velocidade de ataque."),
    _passive("leader_2","epic","Lideranca II","Leader II","+7% de dano ao jogador e aliados.","leader"),
    _passive("sorcerer_1","epic","Canalizacao I","Sorcerer I","-5% de recarga do dominio.","sorcerer"),
    # LENDARIAS
    _passive("tactical_3","legendary","Caca-Gigantes III","Tactical III","+22% de dano contra bosses.","tactical"),
    _passive("collector_3","legendary","Catador III","Collector III","+50% de raio de coleta.","collector"),
    _passive("sorcerer_2","legendary","Canalizacao II","Sorcerer II","-10% recarga do dominio e +5% dano no dominio.","sorcerer"),
    _passive("genius_3","legendary","Aprendizado III","Genius III","Cada upgrade: +4% dano, ate +20%.","genius"),
    _passive("tiny","legendary","Compacto","Tiny","+10% movimento, +8% ataque e hitbox -8%."),
    _passive("giant","legendary","Colossal","Giant","+20% dano, +15% HP e -10% movimento."),
    _passive("tank","legendary","Tanque","Tank","+25% HP, -8% dano recebido e -12% movimento."),
    _passive("diligent_2","legendary","Persistencia II","Diligent II","Cada wave: +3% HP, ate +18%; nao cura.","diligent"),
    _passive("lucky_2","legendary","Precisao II","Lucky II","+6 pontos percentuais de critico.","precision"),
    # MITICAS
    _passive("draconic","mythic","Sangue Draconico","Draconic","+12% dano, +10% moedas, +15% coleta, -5% ataque."),
    _passive("solid_gold","mythic","Ouro Macico","Solid Gold","+15% dano, +20% moedas e -8% movimento."),
    _passive("prodigy","mythic","Prodigio","Prodigy","Cada upgrade: +3% dano e +2% HP; tetos +18%/+12%."),
    _passive("sorcerer_3","mythic","Canalizacao III","Sorcerer III","-15% recarga do dominio e +10% dano no dominio.","sorcerer"),
    _passive("diligent_3","mythic","Persistencia III","Diligent III","Cada wave: +4% HP, ate +28%; nao cura.","diligent"),
    _passive("lucky_3","mythic","Precisao III","Lucky III","+9 pontos percentuais de critico.","precision"),
    _passive("leader_3","mythic","Comandante","Leader III","+10% dano ao jogador/aliados e -3% dano recebido.","leader"),
    _passive("mercenary","mythic","Mercenario","Mercenary","+18% dano, +15% contra bosses e -25% moedas."),
    _passive("blessing","mythic","Bencao","Blessing","+15% dano, +10% HP e cura 2% ao concluir wave."),
    _passive("ghostly","mythic","Espectral","Ghostly","+12% movimento, -15% dash; apos dash +10% dano por 3s."),
    _passive("ace","mythic","As","Ace","+12 pp critico; criticos causam 1,7x.","precision"),
    # SECRETAS
    _passive("time_lord","secret","Cronomante","Time Lord","-15% recarga de ataque, dash e dominio."),
    _passive("god","secret","Divindade","God","+25% dano, +10% HP, +8% movimento e -10% dominio."),
    _passive("monster","secret","Aberracao","Monster","+35% dano, +15% HP, -10% ataque e -5% movimento."),
    _passive("protagonist","secret","Protagonista","Protagonist","+15% dano/HP; 1x por run sobrevive fatal com 1 HP e 1s protecao."),
    _passive("lightspeed","secret","Relampago","Lightspeed","+18% ataque, +15% movimento e -10% dano."),
    _passive("crew_leader","secret","General","Crew Leader","+15% dano pessoal e +20% dano dos aliados.","leader"),
    _passive("miner","secret","Garimpeiro","Miner","+12% dano, +10% ataque, +20% coleta e +10% moedas."),
    _passive("bounty_hunter","secret","Cacador de Recompensas","Bounty Hunter","+30% contra bosses, +20% moedas e cura 10% ao derrotar boss."),
    # BRILHANTE
    _passive("golden_luck","shiny","Fortuna","Golden Luck","+12 pp critico, +20% moedas; kill critica rende +10% moedas.","precision"),
    # DIVINAS
    _passive("angel","divine","Serafim","Angel","+25% boss, +12% ataque, +10 pp critico e -15% dominio."),
    _passive("demon","divine","Demonio","Demon","+30% dano e +20% dano no dominio; -10% HP."),
    _passive("interstellar","divine","Cosmo","Interstellar","+20% dano, +15% ataque, +10% movimento; dominio +15% duracao e +10% recarga."),
    _passive("broken_limiter","divine","Sem Limites","Broken Limiter","+30% dano, +15% ataque; +10% dano durante dominio."),
    # DEMONIACAS
    _passive("omnipresent","demonic","Onipresenca","Omnipresent","+35% dano, +20% boss, -20% dominio e -15% ataque."),
    _passive("fallen_angel","demonic","Anjo Caido","Fallen Angel","+35% dano, +20% dominio/aliados; recarga dominio +20%."),
    _passive("abyssal_wealth","demonic","Riqueza Abissal","Abyssal Wealth","+35% dano, +40% moedas, -12% movimento; dominio +15% recarga."),
    # ENFRAQUECEDORAS - desafio, nunca roleta normal
    _passive("weak","weakening","Fragil","Weak","-10% de dano.",rollable=False),
    _passive("slow","weakening","Pesado","Slow","-8% de movimento; dash inalterado.",rollable=False),
    _passive("dumb","weakening","Inexperiente","Dumb","-10% de moedas.",rollable=False),
]
PASSIVE_BY_KEY = {x["key"]: x for x in PASSIVES}

# Familias que nunca acumulam entre os dois slots.
PASSIVE_FAMILIES = {
    "strong_1":"strong","strong_2":"strong","strong_3":"strong",
    "genius_1":"genius","genius_2":"genius","genius_3":"genius",
    "tactical_1":"tactical","tactical_2":"tactical","tactical_3":"tactical",
    "rich_1":"rich","rich_2":"rich","rich_3":"rich",
    "collector_1":"collector","collector_2":"collector","collector_3":"collector",
    "leader_1":"leader","leader_2":"leader","leader_3":"leader","crew_leader":"leader",
    "diligent_1":"diligent","diligent_2":"diligent","diligent_3":"diligent",
    "sorcerer_1":"sorcerer","sorcerer_2":"sorcerer","sorcerer_3":"sorcerer",
    "lucky_1":"precision","lucky_2":"precision","lucky_3":"precision","ace":"precision","golden_luck":"precision",
}


SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "energia_vital_save.json")

DEFAULT_SAVE = {
    "coins": 0,
    "vitality_level": 0,
    "damage_level": 0,
    "speed_level": 0,
    "stamina_level": 0,
    "regen_level": 0,
    "armor_level": 0,
    "healing_level": 0,
    "domain_level": 0,
    "orb_level": 0,
    "coin_level": 0,
    "dash_level": 0,
    "crit_level": 0,
    "best_wave": 0,
    "best_kills": 0,
    "mode_records": {},
    "kayk_unlocked": False,
    "father_victories": [],
    "father_unlocked": False,
    "sentinel_victories": [],
    "hank_unlocked": False,
    "strikada_unlocked": False,
    "glonk100_unlocked": False,
    "rip_indra_unlocked": False,
    "hisoka_unlocked": False,
    "hisoka_impossible_wave30_chars": [],
    "glonk_deaths": 0,
    "cheat_all_chars": False,
    "unlocked_achievements": [],
    "mission_stats": {},
    "completed_missions": [],
    "total_kills": 0,
    "total_domains": 0,
    "clash_wins": 0,
    "pineapple_refunds": 0,
    "gula_hunger": 0,
    "glonk_last_discovered": False,
    "gula_defeats": 0,
    "sin_defeats": [],
    "cheat_money": False,
    "cheat_dev": False,
    "cheat_immortal": False,
    "cheat_infinite_damage": False,
    "cheat_items_infinite": False,
    "cheat_start_wave": 1,
    "forge_materials": {},
    "forge_discovered": [],
    "crafted_weapons": [],
    "equipped_weapons": {},
    "character_evolution": {},
    "character_passives": {},
    "passive_discovered": ["first_friend"],
    "upgrade_discovered": [],
    "passive_auto_stop_rarities": [],
    "passive_auto_stop_keys": [],
    "control_layout": {},
    "sfx_on": True,
    "music_on": True,
    "sfx_volume": 70,
    "music_volume": 30,
}


LEGACY_COLOSSUS_NAME = "".join(("Pai", " do ", "Kayk"))

def _migrate_legacy_colossus_name(value):
    """Converte referencias do nome anterior em saves sem quebrar progresso existente."""
    if isinstance(value, dict):
        migrated = {}
        for key, item in value.items():
            new_key = "Colosso do Caos" if key == LEGACY_COLOSSUS_NAME else key
            migrated[new_key] = _migrate_legacy_colossus_name(item)
        return migrated
    if isinstance(value, list):
        return [_migrate_legacy_colossus_name(item) for item in value]
    if isinstance(value, str):
        return value.replace(LEGACY_COLOSSUS_NAME, "Colosso do Caos").replace(LEGACY_COLOSSUS_NAME.upper(), "COLOSSO DO CAOS")
    return value


def load_save():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = _migrate_legacy_colossus_name(data)
        out = DEFAULT_SAVE.copy()
        out.update(data)
        if "sfx_volume" not in data:
            out["sfx_volume"] = 70 if bool(data.get("sfx_on", True)) else 0
        if "music_volume" not in data:
            out["music_volume"] = 30 if bool(data.get("music_on", True)) else 0
        out["sfx_volume"] = int(max(0, min(100, out.get("sfx_volume",70))))
        out["music_volume"] = int(max(0, min(100, out.get("music_volume",30))))
        out["sfx_on"] = out["sfx_volume"] > 0
        out["music_on"] = out["music_volume"] > 0
        return out
    except Exception:
        return DEFAULT_SAVE.copy()


def save_data(data):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def passive_character_profile(character):
    """Perfil persistente SEM inventario: existem somente 2 slots por personagem."""
    if is_beta_character(character):
        return {"equipped": [None, None]}
    root = SAVE.get("character_passives")
    if not isinstance(root, dict):
        root = {}; SAVE["character_passives"] = root
    prof = root.get(character)
    new_profile = not isinstance(prof, dict)
    if new_profile:
        prof = {}; root[character] = prof
    equipped = prof.get("equipped")
    if not isinstance(equipped, list): equipped=[]
    while len(equipped)<2: equipped.append(None)
    equipped=equipped[:2]
    equipped=[k if k in PASSIVE_BY_KEY else None for k in equipped]
    # Sanitiza saves da versao antiga: duas passivas da mesma familia ou duas
    # exclusivas de alto nivel nao podem permanecer equipadas juntas.
    if equipped[0] and equipped[1]:
        fam0=passive_family(equipped[0]); fam1=passive_family(equipped[1])
        same_family=bool(fam0 and fam1 and fam0==fam1)
        both_high=(PASSIVE_BY_KEY[equipped[0]]["rarity"] in PASSIVE_HIGH_EXCLUSIVE and PASSIVE_BY_KEY[equipped[1]]["rarity"] in PASSIVE_HIGH_EXCLUSIVE)
        if same_family or both_high:
            equipped[1]=None
    # Migra saves antigos: o inventario antigo e ignorado e removido.
    prof.pop("owned", None)
    # Todo personagem normal nasce com First Friend no slot 1 apenas se nunca teve slots configurados.
    if new_profile and equipped[0] is None and equipped[1] is None:
        equipped[0]="first_friend"
    prof["equipped"]=equipped
    discovered=SAVE.get("passive_discovered")
    if not isinstance(discovered,list): discovered=[]
    if "first_friend" not in discovered: discovered.append("first_friend")
    SAVE["passive_discovered"]=discovered
    return prof


def passive_equipped_keys(character):
    return [k for k in passive_character_profile(character).get("equipped",[]) if k in PASSIVE_BY_KEY]


def passive_family(key):
    if key in PASSIVE_FAMILIES: return PASSIVE_FAMILIES[key]
    item=PASSIVE_BY_KEY.get(key,{})
    return item.get("family")


def passive_roll_key(character):
    """Sorteia raridade pelas chances oficiais e, dentro dela, uma passiva."""
    roll=random.random()*100.0; acc=0.0; rarity="common"
    for r in PASSIVE_ROLL_ORDER:
        acc += PASSIVE_RARITIES[r]["chance"]
        if roll <= acc:
            rarity=r; break
    pool=[x for x in PASSIVES if x["rarity"]==rarity and x.get("rollable",True)]
    return random.choice(pool)["key"] if pool else "strong_1"


def passive_set_slot(character, key, slot):
    """Substitui diretamente um slot. Nao existe inventario/reserva de passivas."""
    if is_beta_character(character) or key not in PASSIVE_BY_KEY or slot not in (0,1):
        return False, None
    pp=passive_character_profile(character)
    eq=list(pp["equipped"])
    other_i=1-slot; other=eq[other_i]
    cleared=None
    # A passiva NOVA tem prioridade. Se conflitar, o outro slot e perdido/esvaziado.
    if other:
        fam=passive_family(key); ofam=passive_family(other)
        conflict_family=bool(fam and ofam and fam==ofam)
        conflict_high=(PASSIVE_BY_KEY[key]["rarity"] in PASSIVE_HIGH_EXCLUSIVE and
                       PASSIVE_BY_KEY[other]["rarity"] in PASSIVE_HIGH_EXCLUSIVE)
        if conflict_family or conflict_high:
            eq[other_i]=None; cleared=other
    eq[slot]=key
    pp["equipped"]=eq
    disc=SAVE.get("passive_discovered",[])
    if not isinstance(disc,list): disc=[]
    if key not in disc: disc.append(key)
    SAVE["passive_discovered"]=disc
    return True, cleared


def passive_auto_stop_hit(key):
    item=PASSIVE_BY_KEY.get(key)
    if not item: return False
    rar=SAVE.get("passive_auto_stop_rarities",[])
    keys=SAVE.get("passive_auto_stop_keys",[])
    if not isinstance(rar,list): rar=[]
    if not isinstance(keys,list): keys=[]
    return item["rarity"] in rar or key in keys

def passive_static_effects(keys):
    """Soma somente efeitos estaticos. Tetos sao aplicados ao final."""
    e={
        "damage":0.0,"boss_damage":0.0,"coins":0.0,"collect":0.0,"crit":0.0,"crit_mult":1.5,
        "move":0.0,"attack_speed":0.0,"attack_recharge":0.0,"hp":0.0,"damage_reduction":0.0,
        "domain_recharge":0.0,"domain_damage":0.0,"domain_duration":0.0,"dash_recharge":0.0,
        "ally_damage":0.0,"wave_heal":0.0,"crit_kill_coins":0.0,"hitbox_scale":1.0,
        "fatal_save":False,
    }
    K=set(keys)
    # simples / familias
    dmg={"strong_1":.05,"strong_2":.10,"strong_3":.15,"first_friend":.03,"draconic":.12,"solid_gold":.15,
         "mercenary":.18,"blessing":.15,"god":.25,"monster":.35,"protagonist":.15,"lightspeed":-.10,
         "miner":.12,"demon":.30,"interstellar":.20,"broken_limiter":.30,"omnipresent":.35,
         "fallen_angel":.35,"abyssal_wealth":.35,"weak":-.10}
    for k,v in dmg.items():
        if k in K:e["damage"]+=v
    boss={"tactical_1":.08,"tactical_2":.15,"tactical_3":.22,"mercenary":.15,"bounty_hunter":.30,"angel":.25,"omnipresent":.20}
    for k,v in boss.items():
        if k in K:e["boss_damage"]+=v
    coins={"rich_1":.05,"rich_2":.10,"rich_3":.15,"draconic":.10,"solid_gold":.20,"mercenary":-.25,
           "miner":.10,"bounty_hunter":.20,"golden_luck":.20,"abyssal_wealth":.40,"dumb":-.10}
    for k,v in coins.items():
        if k in K:e["coins"]+=v
    collect={"collector_1":.15,"collector_2":.30,"collector_3":.50,"draconic":.15,"miner":.20}
    for k,v in collect.items():
        if k in K:e["collect"]+=v
    crit={"lucky_1":.03,"lucky_2":.06,"lucky_3":.09,"ace":.12,"golden_luck":.12,"angel":.10}
    for k,v in crit.items():
        if k in K:e["crit"]+=v
    if "ace" in K:e["crit_mult"]=1.7
    move={"speedy":.10,"tiny":.10,"giant":-.10,"tank":-.12,"solid_gold":-.08,"ghostly":.12,"god":.08,
          "monster":-.05,"lightspeed":.15,"interstellar":.10,"abyssal_wealth":-.12,"slow":-.08}
    for k,v in move.items():
        if k in K:e["move"]+=v
    atk={"speedy":.08,"tiny":.08,"draconic":-.05,"lightspeed":.18,"miner":.10,"angel":.12,"interstellar":.15,
         "broken_limiter":.15,"monster":-.10,"omnipresent":-.15}
    for k,v in atk.items():
        if k in K:e["attack_speed"]+=v
    hp={"first_friend":.05,"giant":.15,"tank":.25,"blessing":.10,"god":.10,"monster":.15,"protagonist":.15,"demon":-.10}
    for k,v in hp.items():
        if k in K:e["hp"]+=v
    if "tank" in K:e["damage_reduction"]+=.08
    if "leader_3" in K:e["damage_reduction"]+=.03
    domain_cd={"sorcerer_1":.05,"sorcerer_2":.10,"sorcerer_3":.15,"time_lord":.15,"god":.10,"angel":.15,
               "omnipresent":.20,"interstellar":-.10,"fallen_angel":-.20,"abyssal_wealth":-.15}
    for k,v in domain_cd.items():
        if k in K:e["domain_recharge"]+=v
    domain_dmg={"sorcerer_2":.05,"sorcerer_3":.10,"demon":.20,"fallen_angel":.20}
    for k,v in domain_dmg.items():
        if k in K:e["domain_damage"]+=v
    if "interstellar" in K:e["domain_duration"]+=.15
    if "time_lord" in K:
        e["dash_recharge"]+=.15
        e["attack_recharge"]+=.15
    if "ghostly" in K:e["dash_recharge"]+=.15
    ally={"leader_1":.04,"leader_2":.07,"leader_3":.10,"crew_leader":.20,"fallen_angel":.20}
    for k,v in ally.items():
        if k in K:e["ally_damage"]+=v
    # Liderancas tambem afetam o proprio jogador, exceto General que tem valor proprio de +15%.
    self_leader={"leader_1":.04,"leader_2":.07,"leader_3":.10,"crew_leader":.15}
    for k,v in self_leader.items():
        if k in K:e["damage"]+=v
    if "blessing" in K:e["wave_heal"]=.02
    if "golden_luck" in K:e["crit_kill_coins"]=.10
    if "tiny" in K:e["hitbox_scale"]=.92
    if "protagonist" in K:e["fatal_save"]=True
    # Tetos SOMENTE nos bonus vindos das passivas.
    e["damage"] = max(-0.90, min(.60, e["damage"]))
    e["attack_speed"] = max(-0.90, min(.30, e["attack_speed"]))
    e["attack_recharge"] = max(0.0, min(.25, e["attack_recharge"]))
    e["move"] = max(-0.90, min(.25, e["move"]))
    e["domain_recharge"] = max(-0.90, min(.25, e["domain_recharge"]))
    e["dash_recharge"] = max(0.0, min(.25, e["dash_recharge"]))
    e["crit"] = max(0.0, min(.15, e["crit"]))
    return e


def is_beta_character(character):
    return character in BETA_CHARACTER_ORDER


def evolution_profile(character):
    """Retorna/cria a progressao persistente. Personagens beta nao possuem progressao."""
    if is_beta_character(character):
        return {"points": 0, "earned": 0, **{key: 0 for key in EVOLUTION_STAT_KEYS}}
    root = SAVE.get("character_evolution")
    if not isinstance(root, dict):
        root = {}
        SAVE["character_evolution"] = root
    prof = root.get(character)
    if not isinstance(prof, dict):
        prof = {}
        root[character] = prof
    prof.setdefault("points", 0)
    prof.setdefault("earned", 0)
    for key in EVOLUTION_STAT_KEYS:
        prof.setdefault(key, 0)
        try:
            prof[key] = int(clamp(int(prof[key]), 0, MAX_EVOLUTION_STAT))
        except Exception:
            prof[key] = 0
    try:
        prof["points"] = max(0, int(prof["points"]))
        prof["earned"] = max(0, int(prof["earned"]))
    except Exception:
        prof["points"], prof["earned"] = 0, 0
    return prof


def evolution_level(character):
    if is_beta_character(character):
        return 1
    prof = evolution_profile(character)
    return 1 + sum(int(prof.get(k, 0)) for k in EVOLUTION_STAT_KEYS)


def evolution_drop_chance(wave):
    # V14: toda onda vencida concede 1 Ponto de Evolucao garantido.
    return 1.0


def evolution_rating(character, stat):
    base = CHARACTER_BASE_RATINGS.get(character, {}).get(stat, 1)
    if is_beta_character(character):
        return base
    return base + evolution_profile(character).get(stat, 0)


BACKUP_PREFIX = "EV11"

def make_backup_code(data):
    """Transforma o save inteiro em um codigo portatil e verificavel."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    packed = zlib.compress(raw, 9)
    payload = base64.urlsafe_b64encode(packed).decode("ascii").rstrip("=")
    checksum = hashlib.sha256(packed).hexdigest()[:10].upper()
    return f"{BACKUP_PREFIX}-{payload}-{checksum}"

def restore_backup_code(code):
    """Valida e converte um codigo de backup em SAVE compatível com esta versao."""
    clean = "".join(str(code).strip().split())
    if not clean.startswith(BACKUP_PREFIX + "-"):
        raise ValueError("VERSAO DE BACKUP INVALIDA")
    try:
        _prefix, payload, checksum = clean.split("-", 2)
        # O payload Base64URL tambem pode conter '-', portanto separa o checksum pela direita.
        payload, checksum = clean[len(BACKUP_PREFIX)+1:].rsplit("-", 1)
        padded = payload + "=" * ((4 - len(payload) % 4) % 4)
        packed = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:
        raise ValueError("CODIGO MALFORMADO") from exc
    if hashlib.sha256(packed).hexdigest()[:10].upper() != checksum.upper():
        raise ValueError("CODIGO CORROMPIDO")
    try:
        raw = zlib.decompress(packed)
        if len(raw) > 200000:
            raise ValueError("BACKUP GRANDE DEMAIS")
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError("DADOS INVALIDOS") from exc
    if not isinstance(data, dict):
        raise ValueError("SAVE INVALIDO")
    restored = DEFAULT_SAVE.copy()
    for key in DEFAULT_SAVE:
        if key in data:
            restored[key] = data[key]
    return restored

def _android_clipboard():
    """Retorna (activity, ClipboardManager, ClipData) usando a API nativa do Android."""
    if not IS_ANDROID:
        return None
    try:
        # Import local: no desktop/janela de teste o jogo continua funcionando mesmo sem pyjnius.
        from jnius import autoclass
        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        ClipData = autoclass("android.content.ClipData")
        activity = PythonActivity.mActivity
        if activity is None:
            return None
        manager = activity.getSystemService(Context.CLIPBOARD_SERVICE)
        if manager is None:
            return None
        return activity, manager, ClipData
    except Exception:
        return None

def clipboard_put_text(text):
    value = str(text)

    # Android: usa o ClipboardManager real. pygame.scrap/SDL pode reportar sucesso
    # sem efetivamente preencher o clipboard em alguns aparelhos.
    native = _android_clipboard()
    if native is not None:
        try:
            activity, manager, ClipData = native
            manager.setPrimaryClip(ClipData.newPlainText("Energia Vital - Backup", value))
            # Verifica lendo o clipboard de volta. So retorna True se realmente copiou.
            clip = manager.getPrimaryClip()
            if clip is not None and clip.getItemCount() > 0:
                got = clip.getItemAt(0).coerceToText(activity)
                if got is not None and str(got).strip() == value.strip():
                    return True
        except Exception:
            pass

    # Fallback para desktop e aparelhos onde o bridge Android nao estiver disponivel.
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        encoded = value.encode("utf-8")
        pygame.scrap.put(pygame.SCRAP_TEXT, encoded + b"\x00")
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if raw:
            if isinstance(raw, bytes):
                check = raw.decode("utf-8", "ignore").replace("\x00", "").strip()
            else:
                check = str(raw).strip()
            return check == value.strip()
    except Exception:
        pass
    return False

def clipboard_get_text():
    # Primeiro tenta o clipboard nativo do Android.
    native = _android_clipboard()
    if native is not None:
        try:
            activity, manager, _ClipData = native
            clip = manager.getPrimaryClip()
            if clip is not None and clip.getItemCount() > 0:
                got = clip.getItemAt(0).coerceToText(activity)
                if got is not None:
                    value = str(got).strip()
                    if value:
                        return value
        except Exception:
            pass

    # Fallback SDL/Pygame.
    try:
        if not pygame.scrap.get_init():
            pygame.scrap.init()
        raw = pygame.scrap.get(pygame.SCRAP_TEXT)
        if not raw:
            return None
        if isinstance(raw, bytes):
            return raw.decode("utf-8", "ignore").replace("\x00", "").strip()
        return str(raw).strip()
    except Exception:
        return None

SAVE = load_save()
# V13 FINAL: limite real de 30 niveis para upgrades permanentes, inclusive em saves antigos.
for _perm_key, _perm_name, _perm_desc, _perm_base in PERMANENT_UPGRADES:
    SAVE[_perm_key] = max(0, min(PERMANENT_UPGRADE_CAP, int(SAVE.get(_perm_key, 0) or 0)))
# Migracao: builds anteriores guardavam o fragmento da Gula como gula_shard.
_old_mats = SAVE.setdefault("forge_materials", {})
if isinstance(_old_mats, dict) and _old_mats.get("gula_shard", 0):
    _old_mats["sin_gula"] = int(_old_mats.get("sin_gula", 0)) + int(_old_mats.pop("gula_shard", 0))
    save_data(SAVE)
AUDIO = AudioManager(SAVE)


def clamp(v, a, b):
    return max(a, min(b, v))


def vec_from_angle(a):
    return pygame.Vector2(math.cos(a), math.sin(a))


def point_segment_distance(point, a, b):
    p = pygame.Vector2(point); a = pygame.Vector2(a); b = pygame.Vector2(b)
    ab = b - a
    if ab.length_squared() <= 0.0001:
        return p.distance_to(a)
    t = clamp((p-a).dot(ab) / ab.length_squared(), 0.0, 1.0)
    return p.distance_to(a + ab*t)


def ray_to_arena_edge(origin, direction):
    origin = pygame.Vector2(origin); d = pygame.Vector2(direction)
    if d.length_squared() <= 0.0001:
        d = pygame.Vector2(1, 0)
    d = d.normalize()
    top, bottom = S(165), H-S(335)
    candidates = []
    if d.x > 0: candidates.append((W-origin.x)/d.x)
    elif d.x < 0: candidates.append((0-origin.x)/d.x)
    if d.y > 0: candidates.append((bottom-origin.y)/d.y)
    elif d.y < 0: candidates.append((top-origin.y)/d.y)
    valid = [t for t in candidates if t > 0]
    t = min(valid) if valid else max(W,H)
    return origin + d*t


def hank_range_endpoint(origin, direction):
    """Alcance fixo do Hank: 65% do RAIO util da arena, nao 65% do que sobra ate a parede.

    Isso impede que, quando Hank esta no centro, a mira pareca atravessar o mapa inteiro.
    O ponto final ainda e limitado pela parede se ela estiver mais perto.
    """
    origin = pygame.Vector2(origin); d = pygame.Vector2(direction)
    if d.length_squared() <= 0.0001:
        d = pygame.Vector2(1, 0)
    d = d.normalize()
    top, bottom = S(165), H-S(335)
    arena_radius = math.hypot(W*0.5, max(S(120), (bottom-top)*0.5))
    fixed_range = max(S(220), arena_radius * 0.65)
    edge = ray_to_arena_edge(origin, d)
    wall_distance = origin.distance_to(edge)
    return origin + d * min(fixed_range, wall_distance)


def projectile_arena_wall_collision(pr):
    """Resolve hitbox das quatro paredes da arena.

    Retorna True se o projetil pode continuar vivo. `wall_bounce=True` reflete o
    vetor; qualquer outro projetil e destruido ao tocar a parede. Usa o proprio
    raio do projetil para impedir que a arte atravesse visualmente a borda.
    """
    r = max(1, float(getattr(pr, "radius", S(8))))
    left, right = r, W-r
    top, bottom = S(165)+r, H-S(335)-r
    hit_x = pr.pos.x < left or pr.pos.x > right
    hit_y = pr.pos.y < top or pr.pos.y > bottom
    if not hit_x and not hit_y:
        return True
    if not getattr(pr, "wall_bounce", False):
        return False
    if hit_x:
        pr.pos.x = clamp(pr.pos.x, left, right)
        pr.vel.x *= -1
    if hit_y:
        pr.pos.y = clamp(pr.pos.y, top, bottom)
        pr.vel.y *= -1
    return True


def draw_bone_rect(center, direction, length, width, color=WHITE):
    """Osso retangular leve: usado no projetil e no golpe corpo a corpo do Sans."""
    c = pygame.Vector2(center)
    d = pygame.Vector2(direction)
    if d.length_squared() <= 0.0001:
        d = pygame.Vector2(1, 0)
    d = d.normalize()
    p = pygame.Vector2(-d.y, d.x)
    hl = length * 0.5
    hw = width * 0.5
    pts = [c-d*hl-p*hw, c+d*hl-p*hw, c+d*hl+p*hw, c-d*hl+p*hw]
    # contorno escuro + corpo branco para continuar legivel no fundo claro/azul.
    outer = [c-d*(hl+S(2))-p*(hw+S(2)), c+d*(hl+S(2))-p*(hw+S(2)),
             c+d*(hl+S(2))+p*(hw+S(2)), c-d*(hl+S(2))+p*(hw+S(2))]
    pygame.draw.polygon(SCREEN, DARK, outer)
    pygame.draw.polygon(SCREEN, color, pts)


def beam_hits_point_fast(point, start, direction, beam_length, half_width):
    """Colisao de feixe sem criar varios Vector2; reduz pico de frame do Blaster."""
    px, py = point.x-start.x, point.y-start.y
    along = px*direction.x + py*direction.y
    if along < 0 or along > beam_length:
        return False
    lateral = abs(px*direction.y - py*direction.x)
    return lateral <= half_width


def draw_text(text, font, color, pos, center=False):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    SCREEN.blit(img, rect)
    return rect

def draw_wrapped_text(text, font, color, rect, line_gap=4, center=False, max_lines=None):
    """Desenha texto quebrado em linhas sem depender de fontes externas."""
    words = str(text).split()
    lines, current = [], ""
    for word in words:
        test = word if not current else current + " " + word
        if font.size(test)[0] <= rect.w or not current:
            current = test
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    if max_lines is not None:
        lines = lines[:max_lines]
    y = rect.y
    for line in lines:
        img = font.render(line, True, color)
        x = rect.centerx - img.get_width()/2 if center else rect.x
        SCREEN.blit(img, (x, y))
        y += img.get_height() + S(line_gap)
    return y


def circle_button(rect, label, color):
    center = rect.center
    radius = min(rect.w, rect.h) // 2
    pygame.draw.circle(SCREEN, color, center, radius)
    pygame.draw.circle(SCREEN, WHITE, center, radius, S(4))
    draw_text(label, FONT_S, WHITE, center, True)


@dataclass
class DamageText:
    text: str
    pos: pygame.Vector2
    color: tuple
    life: float = 0.65

    def update(self, dt):
        self.life -= dt
        self.pos.y -= S(70) * dt
        return self.life > 0

    def draw(self, offset):
        alpha = clamp(int(255 * self.life / 0.65), 0, 255)
        img = FONT_S.render(self.text, True, self.color)
        img.set_alpha(alpha)
        SCREEN.blit(img, (self.pos.x + offset.x, self.pos.y + offset.y))


@dataclass
class Particle:
    pos: pygame.Vector2
    vel: pygame.Vector2
    color: tuple
    life: float
    radius: float

    def update(self, dt):
        self.life -= dt
        self.pos += self.vel * dt
        self.vel *= 0.94
        return self.life > 0

    def draw(self, offset):
        if self.life <= 0:
            return
        r = max(1, int(self.radius * max(0.2, self.life)))
        pygame.draw.circle(SCREEN, self.color, (int(self.pos.x + offset.x), int(self.pos.y + offset.y)), r)


class Projectile:
    def __init__(self, pos, vel, damage, owner="enemy", radius=None, color=None, life=4.5, pierce=0):
        self.pos = pygame.Vector2(pos)
        self.vel = pygame.Vector2(vel)
        self.damage = damage
        self.owner = owner
        self.radius = radius or S(10)
        self.color = color or (RED if owner == "enemy" else CYAN)
        self.life = life
        self.pierce = pierce
        self.hit_ids = set()
        # Sistema geral V15: projeteis com wall_bounce refletem nas paredes da arena.
        # Todos os demais param na borda. Futuros personagens so precisam ativar esta flag.
        self.wall_bounce = False
        self.domain_charge_raw = 0.0
        self.domain_charge_uses_left = 0

    def update(self, dt):
        self.pos += self.vel * dt
        self.life -= dt
        return self.life > 0 and -S(100) < self.pos.x < W + S(100) and -S(100) < self.pos.y < H + S(100)

    def draw(self, offset):
        kind = getattr(self, "kind", "")
        if kind == "vinicius_bolt":
            p=self.pos+offset; d=pygame.Vector2(self.vel)
            if d.length_squared()<=0: d=pygame.Vector2(1,0)
            d=d.normalize(); n=pygame.Vector2(-d.y,d.x); hl,hw=S(24),S(7)
            pts=[p+d*hl+n*hw,p+d*hl-n*hw,p-d*hl-n*hw,p-d*hl+n*hw]
            pts=[(int(q.x),int(q.y)) for q in pts]
            pygame.draw.polygon(SCREEN,RED,pts); pygame.draw.polygon(SCREEN,(120,20,30),pts,max(1,S(2))); return
        if kind in ("sans_bone", "sans_bad_time_bone"):
            d = self.vel if self.vel.length_squared() > 0 else pygame.Vector2(1, 0)
            draw_bone_rect(self.pos + offset, d, S(62 if kind == "sans_bone" else 72), S(15), WHITE)
            return
        if kind == "strikada_ball":
            p = self.pos + offset
            r = max(S(10), self.radius)
            pygame.draw.circle(SCREEN, (235, 248, 255), (int(p.x), int(p.y)), r)
            pygame.draw.circle(SCREEN, (125, 220, 255), (int(p.x), int(p.y)), r, max(2, S(3)))
            pygame.draw.line(SCREEN, (125, 220, 255), (int(p.x-r*0.65), int(p.y)), (int(p.x+r*0.65), int(p.y)), max(1,S(2)))
            return
        if kind == "vasco_bet":
            p = self.pos + offset
            r = max(S(9), self.radius)
            pygame.draw.circle(SCREEN, VASCO_GREEN, (int(p.x), int(p.y)), r)
            pygame.draw.circle(SCREEN, VASCO_NEON, (int(p.x), int(p.y)), r, max(2,S(3)))
            pygame.draw.circle(SCREEN, VASCO_NEON, (int(p.x), int(p.y)), max(2,r//4))
            return
        if kind == "hank_shell":
            p = self.pos + offset
            r = max(S(10), self.radius)
            pygame.draw.circle(SCREEN, (210,210,210), (int(p.x), int(p.y)), r)
            pygame.draw.circle(SCREEN, DARK, (int(p.x), int(p.y)), r, max(2,S(3)))
            pygame.draw.circle(SCREEN, RED, (int(p.x), int(p.y)), max(2,r//3))
            return
        if kind in ("hisoka_domain_card",):
            p=self.pos+offset; d=pygame.Vector2(self.vel)
            if d.length_squared()==0: d=pygame.Vector2(1,0)
            d=d.normalize(); n=pygame.Vector2(-d.y,d.x); hl=S(15); hw=S(8)
            pts=[p+d*hl+n*hw,p+d*hl-n*hw,p-d*hl-n*hw,p-d*hl+n*hw]
            pygame.draw.polygon(SCREEN,HISOKA_COLOR,[(int(q.x),int(q.y)) for q in pts]); pygame.draw.polygon(SCREEN,WHITE,[(int(q.x),int(q.y)) for q in pts],max(1,S(2))); return
        if kind == "rip_wave":
            p=self.pos+offset; d=pygame.Vector2(self.vel)
            if d.length_squared()==0: d=pygame.Vector2(1,0)
            d=d.normalize(); n=pygame.Vector2(-d.y,d.x); half=S(52)
            pygame.draw.line(SCREEN,RIP_INDRA_COLOR,(int((p-n*half).x),int((p-n*half).y)),(int((p+n*half).x),int((p+n*half).y)),max(2,S(7))); return
        if kind == "sukuna_slash":
            p=self.pos+offset; d=pygame.Vector2(self.vel)
            if d.length_squared()<=0: d=pygame.Vector2(1,0)
            d=d.normalize(); n=pygame.Vector2(-d.y,d.x)
            half=S(38); thick=S(5)
            a=p-n*half; b=p+n*half
            pygame.draw.line(SCREEN,(255,235,225),(int(a.x),int(a.y)),(int(b.x),int(b.y)),max(2,thick))
            pygame.draw.line(SCREEN,SUKUNA_COLOR,(int((a+n*S(4)).x),int((a+n*S(4)).y)),(int((b-n*S(4)).x),int((b-n*S(4)).y)),max(1,S(2)))
            return
        if kind == "lira_censor":
            # V15 FIX: imagem da censura 2x maior para ficar legivel no celular.
            # A hitbox continua igual; somente o sprite visual foi ampliado.
            p=self.pos+offset; size=max(S(68),self.radius*8); img=censured_projectile_surface(size)
            if img is not None:
                SCREEN.blit(img,img.get_rect(center=(int(p.x),int(p.y))))
            else:
                r=pygame.Rect(int(p.x-size/2),int(p.y-size/4),size,max(S(14),size//2))
                pygame.draw.rect(SCREEN,DARK,r,border_radius=max(1,S(3)))
                pygame.draw.rect(SCREEN,LIRA_ACCENT,r,max(1,S(2)),border_radius=max(1,S(3)))
                draw_text("C#NSUR#",FONT_S,WHITE,r.center,True)
            return
        pygame.draw.circle(SCREEN, self.color, (int(self.pos.x + offset.x), int(self.pos.y + offset.y)), self.radius)
        pygame.draw.circle(SCREEN, WHITE, (int(self.pos.x + offset.x), int(self.pos.y + offset.y)), max(1, self.radius // 3))


class BoomerangProjectile(Projectile):
    """Abacaxi do Pedro: sai, faz a curva e retorna para o jogador."""
    def __init__(self, player, direction, damage, speed_mult=1.0, range_mult=1.0, return_hit=False, explosive=False, crown=False):
        d = pygame.Vector2(direction)
        if d.length_squared() == 0:
            d = pygame.Vector2(1, 0)
        d = d.normalize()
        self.player_ref = player
        self.base_speed = S(560) * speed_mult * (1.15 if getattr(player,"hybrid_kinetic_rebound",False) else 1.0)
        super().__init__(player.pos + d*S(40), d*self.base_speed, damage, "player", S(15), YELLOW, 4.0, 1)
        self.kind = "pineapple"
        self.wall_bounce = True
        self.origin = pygame.Vector2(player.pos)
        self.out_timer = 0.48 * range_mult
        self.returning = False
        self.return_hit = True
        self.hit_any = False
        self.returned_to_player = False
        self.explosive = explosive
        self.crown = crown
        self.spin = 0.0
        self.cleared_for_return = False
        self.saturn = bool(getattr(player,"pedro_saturn",False)); self.saturn_timer = 0.24 if self.saturn else 0.0
        self.predator = bool(getattr(player,"pedro_predator_fruit",False)); self.predator_triggered=False
        self.double_crop = bool(getattr(player,"pedro_double_crop",False)); self.industrial = bool(getattr(player,"pedro_industrial_plantation",False))

    def update(self, dt):
        self.life -= dt
        self.spin += dt * 9.0
        if self.life <= 0:
            return False
        if not self.returning:
            if self.saturn_timer > 0:
                self.saturn_timer=max(0.0,self.saturn_timer-dt)
                self.vel=self.vel.rotate_rad(4.8*dt)
            self.pos += self.vel * dt
            self.out_timer -= dt
            if self.out_timer <= 0:
                self.returning = True
                if not self.cleared_for_return:
                    # Todo abacaxi pode acertar novamente na volta.
                    self.hit_ids.clear()
                    self.cleared_for_return = True
        else:
            target = self.player_ref.pos - self.pos
            dist = target.length()
            if dist <= S(38):
                self.returned_to_player = True
                return False
            if dist > 0:
                desired = target.normalize() * self.base_speed * 1.08
                self.vel = self.vel.lerp(desired, min(1.0, dt*10.0))
            self.pos += self.vel * dt
        return -S(160) < self.pos.x < W+S(160) and -S(160) < self.pos.y < H+S(160)

    def draw(self, offset):
        p = self.pos + offset
        r = self.radius
        # Corpo do abacaxi + folhinhas. Simples e leve para Android.
        pygame.draw.circle(SCREEN, YELLOW, (int(p.x), int(p.y)), r)
        pygame.draw.circle(SCREEN, ORANGE, (int(p.x), int(p.y)), r, max(1, S(2)))
        a = self.spin
        top = pygame.Vector2(math.cos(a), math.sin(a))
        for off in (-0.55, 0.0, 0.55):
            d = vec_from_angle(a-math.pi/2+off)
            end = p + d*S(22)
            pygame.draw.line(SCREEN, GREEN, p, end, max(2, S(4)))


class HisokaCardProjectile(Projectile):
    """Carta do Hisoka: sai e retorna; Aranha Excitante puxa alvos na volta."""
    def __init__(self, player, direction, damage, charged=False, spider=False, return_mult=1.0):
        d=pygame.Vector2(direction)
        if d.length_squared()==0: d=pygame.Vector2(1,0)
        d=d.normalize(); self.player_ref=player; self.charged=charged; self.spider=spider
        self.base_speed=S(980 if charged else (720 if spider else 650))
        radius=S(20 if charged else (12 if spider else 10))
        super().__init__(player.pos+d*S(38),d*self.base_speed,damage,"player",radius,HISOKA_REVIVE_COLOR if spider else HISOKA_COLOR,3.2,0)
        self.kind="hisoka_spider_card" if spider else ("hisoka_charged_card" if charged else "hisoka_card")
        self.origin=pygame.Vector2(player.pos); self.out_timer=0.42 if not charged else 0.55
        self.returning=False; self.cleared_for_return=False; self.return_mult=return_mult; self.returned_to_player=False
        self.domain_charge_raw=20.0; self.domain_charge_uses_left=1
        self.hisoka_stun=2.0 if (charged and getattr(player,"hisoka_paralyzing_joker",False)) else (1.0 if charged else 0.0)
    def update(self,dt):
        self.life-=dt
        if self.life<=0: return False
        if not self.returning:
            self.pos += self.vel*dt; self.out_timer-=dt
            if self.out_timer<=0:
                self.returning=True
                if not self.cleared_for_return:
                    self.hit_ids.clear(); self.cleared_for_return=True
        else:
            target=self.player_ref.pos-self.pos; dist=target.length()
            if dist<=S(36): self.returned_to_player=True; return False
            if dist>0:
                speed=self.base_speed*(1.32 if getattr(self.player_ref,"hisoka_elastic_gum",False) else 1.08)
                self.vel=self.vel.lerp(target.normalize()*speed,min(1.0,dt*12.0))
            self.pos += self.vel*dt
        return -S(150)<self.pos.x<W+S(150) and -S(150)<self.pos.y<H+S(150)
    def draw(self,offset):
        p=self.pos+offset; d=pygame.Vector2(self.vel)
        if d.length_squared()==0: d=pygame.Vector2(1,0)
        d=d.normalize(); n=pygame.Vector2(-d.y,d.x); hl=self.radius*1.35; hw=self.radius*0.72
        pts=[p+d*hl+n*hw,p+d*hl-n*hw,p-d*hl-n*hw,p-d*hl+n*hw]
        pts=[(int(q.x),int(q.y)) for q in pts]
        pygame.draw.polygon(SCREEN,self.color,pts); pygame.draw.polygon(SCREEN,WHITE,pts,max(1,S(2)))
        pygame.draw.circle(SCREEN,DARK,(int(p.x),int(p.y)),max(1,int(self.radius*0.20)))


class RuanServant:
    """Amigo criado por um abate DIRETO do Ruan."""
    NEXT_ID = 1
    def __init__(self, pos, source_enemy, player, guardian=False):
        self.id = RuanServant.NEXT_ID
        RuanServant.NEXT_ID += 1
        self.pos = pygame.Vector2(pos)
        self.guardian = guardian
        self.owner_player = player
        self.dead = False
        self.radius = S(58 if guardian else 24)
        base_hp = max(35.0, min(280.0, getattr(source_enemy, "max_hp", 70) * (0.52 if not guardian else 1.15)))
        self.max_hp = base_hp * player.ruan_servant_hp_mult
        self.hp = self.max_hp
        self.damage = max(9.0, player.base_damage * (2.20 if guardian else 0.58)) * player.ruan_servant_damage_mult * player.passive_ally_damage_mult() * getattr(player,"summon_power_mult",1.0)
        if guardian:
            self.damage *= player.ruan_guardian_mult
            self.max_hp *= player.ruan_guardian_mult
            self.hp = self.max_hp
        self.speed = S(210 if guardian else 165) * player.ruan_servant_speed_mult * getattr(player,"summon_power_mult",1.0)
        self.attack_cd = 0.0
        self.color = CYAN if guardian else GREEN
        self.forge_exact_clone = bool(getattr(player, "forge_ruan", False) and not guardian and hasattr(source_enemy, "kind"))
        self.monarch_traits = bool(getattr(player, "divine_ruan", False) and not guardian and hasattr(source_enemy, "kind"))
        self.clone_kind = getattr(source_enemy, "kind", "chaser") if (self.forge_exact_clone or self.monarch_traits) else "chaser"
        self.clone_elite = getattr(source_enemy, "elite", None) if (self.forge_exact_clone or self.monarch_traits) else None
        if self.forge_exact_clone:
            self.radius = getattr(source_enemy, "radius", self.radius)
            self.max_hp = max(1.0, getattr(source_enemy, "max_hp", self.max_hp))
            self.hp = self.max_hp
            self.speed = getattr(source_enemy, "speed", self.speed)
            self.damage = max(1.0, getattr(source_enemy, "contact_damage", self.damage))
            self.color = getattr(source_enemy, "color", self.color)
        elif self.monarch_traits:
            # MANTO DO MONARCA: o Amigo preserva a identidade funcional da presa
            # sem copiar 100% dos numeros, para continuar balanceado como summon.
            self.radius = max(S(18), min(S(42), int(getattr(source_enemy, "radius", self.radius))))
            self.color = getattr(source_enemy, "color", self.color)
            source_speed = float(getattr(source_enemy, "speed", self.speed))
            self.speed = max(S(105), min(S(255), source_speed * 0.95)) * player.ruan_servant_speed_mult
            if self.clone_kind == "tank":
                self.max_hp *= 1.30; self.hp = self.max_hp; self.damage *= 1.18
            elif self.clone_kind == "shooter":
                self.damage *= 0.92
            elif self.clone_kind == "kiter":
                self.speed *= 1.08; self.damage *= 0.82
            if self.clone_elite == "frenzy":
                self.speed *= 1.22
            elif self.clone_elite == "giant":
                self.max_hp *= 1.28; self.hp = self.max_hp; self.radius = int(self.radius * 1.15)
            elif self.clone_elite == "armored":
                self.max_hp *= 1.18; self.hp = self.max_hp
        self.shield_hits = 2 if (player.ruan_growing_army and not guardian) else (5 if guardian else 0)
        self.divine_orb = bool(getattr(player,"divine_ruan",False) and not guardian)
        self.rage_timer = 0.0
        self.monarch_shoot_cd = random.uniform(0.18, 0.55)
        self.monarch_exploded = False

    def take_damage(self, amount, game):
        if self.dead:
            return
        if self.shield_hits > 0:
            self.shield_hits -= 1
            game.spawn_particles(self.pos, BLUE, 5)
            return
        amount *= max(0.0,1.0-getattr(self.owner_player,"passive_ally_damage_reduction",lambda:0.0)())
        if self.monarch_traits and self.clone_elite == "armored":
            amount *= 0.78
        self.hp -= amount
        game.spawn_particles(self.pos, self.color, 4)
        if self.hp <= 0:
            self.dead = True
            game.spawn_particles(self.pos, GRAY, 12)
            self._monarch_death_trait(game)
            if getattr(self.owner_player,"ruan_no_one_left",False):
                for ally in getattr(game,"servants",[]):
                    if ally is not self and not ally.dead: ally.rage_timer=max(getattr(ally,"rage_timer",0.0),4.0)

    def _monarch_death_trait(self, game):
        # Elite explosivo recrutado pelo Manto conserva sua explosao, agora a favor do jogador.
        if not self.monarch_traits or self.clone_elite != "explosive" or self.monarch_exploded:
            return
        self.monarch_exploded = True
        game.spawn_particles(self.pos, CYAN, 20)
        old = game.current_damage_kind; game.current_damage_kind = "ruan_servant_explosion"
        for enemy in list(game.enemies):
            if not enemy.dead and enemy.pos.distance_to(self.pos) <= S(135):
                enemy.damage(self.damage * 0.90, game, self.pos)
        game.current_damage_kind = old

    def update(self, dt, game):
        if self.dead:
            return False
        self.attack_cd = max(0.0, self.attack_cd-dt)
        self.monarch_shoot_cd = max(0.0, self.monarch_shoot_cd-dt)
        self.rage_timer=max(0.0,getattr(self,"rage_timer",0.0)-dt)
        # V15: Amigos normais NAO desaparecem mais com o tempo.
        # Permanecem entre waves ate realmente morrerem para dano inimigo.
        targets = [e for e in game.enemies if not e.dead]
        if self.guardian:
            targets = [e for e in targets if game.is_in_domain(e.pos)]
        if not targets:
            return True
        target = min(targets, key=lambda e: e.pos.distance_to(self.pos))
        delta = target.pos - self.pos
        dist = max(1.0, delta.length())
        d = delta / dist
        formation=1.0
        if getattr(self.owner_player,"ruan_attack_formation",False):
            close=sum(1 for a in getattr(game,"servants",[]) if a is not self and not a.dead and a.pos.distance_to(self.pos)<=S(145))
            if close: formation=1.25
        if self.rage_timer>0: formation*=1.30

        combat_kind = self.clone_kind if self.monarch_traits else "melee"
        if combat_kind == "shooter":
            # O Amigo atirador tenta manter distancia e dispara projeteis aliados.
            if dist > S(430): self.pos += d * self.speed * formation * dt
            elif dist < S(250): self.pos -= d * self.speed * formation * dt
            if self.monarch_shoot_cd <= 0:
                shot_d = d if d.length_squared()>0 else pygame.Vector2(1,0)
                pr=Projectile(self.pos+shot_d*S(18), shot_d*S(520), self.damage*0.82, "player", S(7), self.color, 2.0, 0)
                pr.kind="ruan_servant_shot"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=0.0; pr.domain_charge_uses_left=0
                game.projectiles.append(pr)
                self.monarch_shoot_cd = 0.72 if self.clone_elite=="frenzy" else 1.00
                AUDIO.play("hit",0.16,70)
                if self.divine_orb and random.random()<0.035: game.drops.append(Drop(self.pos,"friend_heal"))
        elif combat_kind == "kiter":
            tangent=pygame.Vector2(-d.y,d.x)
            move=(-d*0.70+tangent*0.72) if dist<S(350) else (d*0.25+tangent*0.82)
            if move.length_squared()>0: self.pos += move.normalize()*self.speed*formation*dt
            if self.monarch_shoot_cd <= 0:
                base=math.atan2(d.y,d.x)
                for off in (-0.13,0.13):
                    sd=vec_from_angle(base+off)
                    pr=Projectile(self.pos+sd*S(18),sd*S(500),self.damage*0.58,"player",S(6),self.color,2.0,0)
                    pr.kind="ruan_servant_shot"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=0.0; pr.domain_charge_uses_left=0
                    game.projectiles.append(pr)
                self.monarch_shoot_cd = 0.95 if self.clone_elite=="frenzy" else 1.30
                if self.divine_orb and random.random()<0.035: game.drops.append(Drop(self.pos,"friend_heal"))
        else:
            if dist > self.radius + target.radius + S(12):
                self.pos += d * self.speed * formation * dt
            elif self.attack_cd <= 0:
                old = game.current_damage_kind
                game.current_damage_kind = "ruan_guardian" if self.guardian else "ruan_servant"
                attack_mult=1.0
                if getattr(self.owner_player,"ruan_attack_formation",False) and any(a is not self and not a.dead and a.pos.distance_to(self.pos)<=S(145) for a in getattr(game,"servants",[])): attack_mult*=1.25
                if self.rage_timer>0: attack_mult*=1.40
                target.damage(self.damage*attack_mult, game, self.pos)
                game.current_damage_kind = old
                self.attack_cd = 0.38 if self.guardian else (0.52 if self.clone_elite=="frenzy" and self.monarch_traits else 0.72)
                AUDIO.play("hit", 0.24, 70)
                if getattr(self, "divine_orb", False) and random.random() < 0.055:
                    game.drops.append(Drop(self.pos,"friend_heal"))
        self.pos.x = clamp(self.pos.x, self.radius, W-self.radius)
        self.pos.y = clamp(self.pos.y, S(175)+self.radius, H-S(340)-self.radius)
        if self.guardian and game.domain_active:
            # O guardiao e um efeito do Dominio: ele nao pode sair do circulo fixo.
            delta = self.pos - game.domain_center
            max_dist = max(S(20), game.domain_radius - self.radius - S(8))
            if delta.length() > max_dist:
                self.pos = game.domain_center + delta.normalize() * max_dist
        return not self.dead

    def draw(self, offset):
        p = self.pos + offset
        pygame.draw.circle(SCREEN, self.color, (int(p.x), int(p.y)), self.radius)
        pygame.draw.circle(SCREEN, WHITE, (int(p.x), int(p.y)), self.radius, max(2, S(3)))
        if self.forge_exact_clone:
            pygame.draw.circle(SCREEN, WHITE, (int(p.x), int(p.y)), self.radius, max(1,S(2)))
            draw_text("AMIGO", FONT_S, DARK, (int(p.x), int(p.y)), True)
        else:
            draw_text("GUARDIAO" if self.guardian else "AMIGO", FONT_S, DARK, (int(p.x), int(p.y)), True)
        bw = self.radius*2
        pygame.draw.rect(SCREEN, DARK, (p.x-bw/2, p.y-self.radius-S(13), bw, S(6)))
        pygame.draw.rect(SCREEN, GREEN, (p.x-bw/2, p.y-self.radius-S(13), bw*clamp(self.hp/max(1,self.max_hp),0,1), S(6)))


class MiniAna:
    """Pequena invocacao do cajado da Ana. Corre ate o alvo e explode em area."""
    def __init__(self, pos, damage, index=0, count=1, speed_mult=1.0, blast_mult=1.0, double_chance=0.0):
        self.pos = pygame.Vector2(pos)
        self.damage = damage
        self.radius = S(16)
        self.speed = S(115) * speed_mult
        self.blast_radius = S(135) * blast_mult
        self.life = None  # V8: sem tempo de vida; fica ate atingir/explodir
        self.dead = False
        self.double_chance = double_chance
        self.travel = 0.0
        self.index = index
        self.count = count
        self.domain_charge_raw = 20.0 / max(1, int(count))

    def explode(self, game):
        if self.dead:
            return
        self.dead = True
        domain_boost = game.player.character == "Ana" and game.is_in_domain(self.pos)
        radius = self.blast_radius * (1.70 if domain_boost else 1.0)
        damage = self.damage * (2.50 if domain_boost else 1.0)
        if domain_boost and game.player.ana_reality_exe:
            radius *= 1.20
            damage *= 1.20
        AUDIO.play("ana_explode", 0.85, 45)
        game.spawn_particles(self.pos, PINK, 18)
        game.shake = max(game.shake, S(10))
        hit_any = False
        old_kind = game.current_damage_kind
        game.current_damage_kind = "staff_miniana"
        for enemy in list(game.enemies):
            if enemy.dead:
                continue
            dist = enemy.pos.distance_to(self.pos)
            if dist <= radius + enemy.radius:
                dmg = damage * game.player.effective_damage_mult(game, enemy, "staff", self.travel)
                passive_crit_hit = random.random() < game.player.crit_chance
                if passive_crit_hit:
                    dmg *= game.player.crit_damage_mult
                    game.damage_texts.append(DamageText("CRIT!", pygame.Vector2(enemy.pos), YELLOW))
                was_alive=not enemy.dead
                enemy.damage(dmg, game, self.pos)
                if passive_crit_hit and was_alive and enemy.dead: game.award_passive_critical_kill(enemy)
                if random.random() < self.double_chance:
                    enemy.damage(dmg, game, self.pos)
                    game.damage_texts.append(DamageText("ERRO x2", pygame.Vector2(enemy.pos), PINK))
                hit_any = True
        maho=getattr(game,"mahoraga",None)
        if maho is not None and not maho.dead and maho.pos.distance_to(self.pos) <= radius+maho.radius:
            maho.take_damage(damage,game,self.pos,from_player=True)
            hit_any=True
        game.current_damage_kind = old_kind
        if hit_any:
            game.player.recover_stamina(game.player.stamina_on_hit * 2, game)
            game.register_combo_hit()
            game.domain_charge_primary_hit(self.domain_charge_raw)
        game.shake = max(game.shake, S(8))
        if game.player.character == "Ana" and game.player.ana_continuity and random.random() < 0.30:
            ang=random.random()*math.tau; spawn=game.player.pos+vec_from_angle(ang)*S(48)
            child=MiniAna(spawn, self.damage*0.85, 0, 1, game.player.ana_miniana_speed*game.player.summon_power_mult, game.player.ana_blast_mult, game.player.ana_reality_error)
            if "REALIDADE RECURSIVA" in getattr(game,"synergies",set()): child.speed*=1.25
            game.summons.append(child); game.damage_texts.append(DamageText("CONTINUIDADE",pygame.Vector2(spawn),PINK,0.5))

    def update(self, dt, game):
        if self.dead:
            return False
        # V8: invocacoes da Ana nao expiram por tempo. Isso permite acumular sem limite.
        targets = [e for e in game.enemies if not e.dead]
        domain_boost = game.player.character == "Ana" and game.is_in_domain(self.pos)
        if domain_boost:
            inside = [e for e in targets if game.is_in_domain(e.pos)]
            if inside:
                targets = inside
        if not targets:
            return True
        if game.player.character == "Ana" and game.player.ana_all_ana:
            nearby=[a for a in game.summons if isinstance(a,MiniAna) and not a.dead and a.pos.distance_to(self.pos)<=S(190)]
            center=sum((a.pos for a in nearby),pygame.Vector2())/max(1,len(nearby)) if nearby else self.pos
            target=min(targets,key=lambda e:e.pos.distance_to(center))
        else:
            nearby=[]; target = min(targets, key=lambda e: e.pos.distance_to(self.pos))
        direction = target.pos - self.pos
        dist = direction.length()
        if dist <= target.radius + self.radius + S(10):
            self.explode(game)
            return False
        if dist > 0:
            speed = self.speed * (1.0 + min(0.75,0.10*max(0,len(nearby)-1)))
            step = min(dist, speed * dt)
            self.pos += direction.normalize() * step
            self.travel += step
        return True

    def draw(self, offset):
        p = self.pos + offset
        pygame.draw.circle(SCREEN, PINK, (int(p.x), int(p.y)), self.radius)
        pygame.draw.circle(SCREEN, WHITE, (int(p.x), int(p.y)), self.radius, S(3))
        draw_text("A", FONT_S, DARK, (int(p.x), int(p.y)), True)


class OrbitalAna:
    NEXT_ID=1
    def __init__(self, player):
        self.id=OrbitalAna.NEXT_ID; OrbitalAna.NEXT_ID+=1
        self.player=player
        ring=(self.id-1)//8
        self.radius=S(72)+ring*S(28)
        self.angle=((self.id-1)%8)*math.tau/8
        self.speed=1.8+0.08*((self.id-1)%5)
        self.pos=pygame.Vector2(player.pos)
        self.dead=False
    def update(self,dt,game):
        if self.dead or game.player.hp<=0:
            return False
        self.angle+=self.speed*dt
        self.pos=self.player.pos+vec_from_angle(self.angle)*self.radius
        # Longinus: inimigos comuns continuam sendo eliminados no toque.
        # Bosses NAO sofrem mais HITKILL: cada orb causa 15% do HP maximo (ou um piso baseado no dano da Ana).
        for e in list(game.enemies):
            if not e.dead and e.pos.distance_to(self.pos)<=e.radius+S(15):
                if isinstance(e,Boss):
                    dmg=max(game.player.base_damage*3.0, e.max_hp*0.15)
                    e.damage(dmg,game,self.pos)
                else:
                    e.hp=0
                    e.die(game)
                self.dead=True
                game.spawn_particles(self.pos,DIVINE_BLUE,5)
                return False
        maho=getattr(game,"mahoraga",None)
        if maho is not None and not maho.dead and maho.pos.distance_to(self.pos)<=maho.radius+S(15):
            maho.take_damage(max(game.player.base_damage*3.0,maho.max_hp*0.15),game,self.pos,from_player=True)
            self.dead=True
            game.spawn_particles(self.pos,DIVINE_BLUE,5)
            return False
        return True
    def draw(self,offset):
        p=self.pos+offset
        pygame.draw.circle(SCREEN,PINK,(int(p.x),int(p.y)),S(15))
        pygame.draw.circle(SCREEN,DIVINE_BLUE,(int(p.x),int(p.y)),S(18),max(1,S(3)))
        draw_text("A",FONT_S,WHITE,p,True)

class PlantedPineapple:
    def __init__(self,pos,damage):
        self.pos=pygame.Vector2(pos); self.damage=damage; self.life=25.0; self.tick=0.0; self.radius=S(25)
    def update(self,dt,game):
        self.life-=dt; self.tick-=dt
        if self.life<=0: return False
        if self.pos.distance_to(game.player.pos)<=self.radius+game.player.radius+S(8):
            game.player.heal(10,game); game.damage_texts.append(DamageText("+10 HP",pygame.Vector2(game.player.pos),GREEN,0.7)); return False
        if self.tick<=0:
            self.tick=0.45
            for e in list(game.enemies):
                if not e.dead and e.pos.distance_to(self.pos)<=S(90)+e.radius:
                    e.damage(self.damage,game,self.pos,minimal_fx=True)
        return True
    def draw(self,offset):
        p=self.pos+offset
        pygame.draw.circle(SCREEN,YELLOW,(int(p.x),int(p.y)),self.radius)
        pygame.draw.circle(SCREEN,GREEN,(int(p.x),int(p.y)),self.radius,max(2,S(4)))
        draw_text("P",FONT_S,DARK,p,True)

class Drop:
    COLORS = {"heal": GREEN, "ambient_heal": GREEN, "friend_heal": GREEN, "stamina": CYAN, "shield": BLUE, "haste": YELLOW, "coin": ORANGE}

    def __init__(self, pos, kind):
        self.pos = pygame.Vector2(pos)
        self.kind = kind
        if str(kind).startswith("mat:"):
            self.radius = S(16)
        else:
            self.radius = S(12 if kind in ("ambient_heal","friend_heal") else (20 if kind in ("heal", "stamina") else 18))
        self.t = 0
        self.life = 14 if kind == "ambient_heal" else 12

    def update(self, dt):
        self.t += dt
        self.life -= dt
        return self.life > 0

    def draw(self, offset):
        p = self.pos + pygame.Vector2(0, math.sin(self.t * 5) * S(5)) + offset
        if str(self.kind).startswith("mat:"):
            key = self.kind.split(":",1)[1]
            info = FORGE_MATERIALS.get(key, {})
            rarity = info.get("rarity", "common")
            color = FORGE_RARITIES.get(rarity, ("", GRAY))[1]
            pygame.draw.polygon(SCREEN, color, [(p.x, p.y-self.radius),(p.x+self.radius,p.y),(p.x,p.y+self.radius),(p.x-self.radius,p.y)])
            pygame.draw.polygon(SCREEN, WHITE, [(p.x, p.y-self.radius),(p.x+self.radius,p.y),(p.x,p.y+self.radius),(p.x-self.radius,p.y)], max(1,S(2)))
            draw_text("F", FONT_S, DARK, p, True)
            return
        color = self.COLORS[self.kind]
        # Cura e estamina sao orbes com brilho para ficarem faceis de identificar.
        if self.kind in ("heal", "ambient_heal", "friend_heal", "stamina"):
            pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius + S(7), S(4))
        pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius)
        label = {"heal": "+", "ambient_heal": "+", "friend_heal": "+5", "stamina": "E", "shield": "S", "haste": ">", "coin": "$"}[self.kind]
        draw_text(label, FONT_S, DARK, p, True)


class SansBoneObstacle:
    """Osso giratorio da BAD TIME. Dura alguns segundos e machuca inimigos que cruzarem sua haste."""
    NEXT_ID = 1
    def __init__(self, pos, damage):
        self.id = SansBoneObstacle.NEXT_ID; SansBoneObstacle.NEXT_ID += 1
        self.pos = pygame.Vector2(pos)
        self.length = random.uniform(S(170), S(330))
        self.width = S(13)
        self.angle = random.random()*math.tau
        self.angular_speed = random.choice([-1,1]) * random.uniform(1.3, 2.8)
        self.damage = damage
        self.life = random.uniform(3.0, 4.8)
        self.hit_cd = {}

    def endpoints(self):
        d = vec_from_angle(self.angle) * (self.length*0.5)
        return self.pos-d, self.pos+d

    def update(self, dt, game):
        self.life -= dt
        self.angle += self.angular_speed*dt
        self.hit_cd = {k:max(0.0,v-dt) for k,v in self.hit_cd.items() if v-dt > 0}
        a,b = self.endpoints()
        old = game.current_damage_kind
        game.current_damage_kind = "sans_bad_time_bone"
        for e in list(game.enemies):
            if e.dead or self.hit_cd.get(e.id,0) > 0:
                continue
            if point_segment_distance(e.pos, a, b) <= self.width + e.radius:
                e.damage(self.damage, game, self.pos)
                self.hit_cd[e.id] = 0.48
        game.current_damage_kind = old
        return self.life > 0

    def draw(self, offset):
        # Um unico retangulo giratorio: sem bolinhas nas pontas para nao parecer circular.
        d = vec_from_angle(self.angle)
        draw_bone_rect(self.pos + offset, d, self.length, max(S(14), self.width*2), WHITE)



class ForgeFireTrail:
    def __init__(self, pos, damage):
        self.pos = pygame.Vector2(pos)
        self.damage = damage
        self.radius = S(34)
        self.life = 1.35
        self.tick = 0.0
    def update(self, dt, game):
        self.life -= dt; self.tick -= dt
        if self.tick <= 0:
            self.tick = 0.28
            old=game.current_damage_kind; game.current_damage_kind="forge_fire"
            for e in list(game.enemies):
                if not e.dead and e.pos.distance_to(self.pos) <= self.radius+e.radius:
                    e.damage(self.damage, game, self.pos, minimal_fx=True)
            game.current_damage_kind=old
        return self.life > 0
    def draw(self, offset):
        p=self.pos+offset
        alpha=max(0.15,min(1.0,self.life/1.35))
        r=max(S(8),int(self.radius*alpha))
        pygame.draw.circle(SCREEN, ORANGE, (int(p.x),int(p.y)), r)
        pygame.draw.circle(SCREEN, RED, (int(p.x),int(p.y)), max(S(4),r//2))


SIN_SEQUENCE = [
    {"key":"wrath","name":"IRA","fragment":"sin_wrath","color":RED},
    {"key":"pride","name":"ORGULHO","fragment":"sin_pride","color":YELLOW},
    {"key":"envy","name":"INVEJA","fragment":"sin_envy","color":GREEN},
    {"key":"greed","name":"GANANCIA","fragment":"sin_greed","color":ORANGE},
    {"key":"gula","name":"GULA","fragment":"sin_gula","color":(135,25,50)},
    {"key":"sloth","name":"PREGUICA","fragment":"sin_sloth","color":BLUE},
    {"key":"lust","name":"LUXURIA","fragment":"sin_lust","color":PINK},
]

def sin_encounter_for_wave(wave):
    """V14: 35=Arcebispo da Ira, 40=Ira, 45=Arcebispo do Orgulho ... 95=Arcebispo da Luxuria, 100=Luxuria. Depois reinicia mais forte."""
    if wave < 35 or (wave - 35) % 5 != 0:
        return None
    slot = ((wave - 35) // 5) % 14
    sin_index = slot // 2
    is_archbishop = (slot % 2 == 0)
    return SIN_SEQUENCE[sin_index], is_archbishop

VINICIUS_QUOTES = [
    "Olha só essa Farm davizão",
    "Isso que é automático.",
    "FALA GALERA EAI BLZ?",
    "Só vou fazer mais uma vez",
]

class ViniciusWall:
    NEXT_ID = 900000
    def __init__(self, pos, hp=180):
        self.id=ViniciusWall.NEXT_ID; ViniciusWall.NEXT_ID+=1
        self.pos=pygame.Vector2(pos); self.max_hp=float(hp); self.hp=float(hp); self.radius=S(42); self.dead=False; self.taunt=True
    def take_damage(self, amount, game):
        if self.dead: return
        self.hp-=amount; self.since_hit=0.0
        if self.hp<=0: self.dead=True; game.spawn_particles(self.pos,GRAY,10)
    def update(self,dt,game): return not self.dead
    def draw(self,offset):
        p=self.pos+offset; r=pygame.Rect(int(p.x-self.radius),int(p.y-self.radius),self.radius*2,self.radius*2)
        pygame.draw.rect(SCREEN,(105,110,125),r,border_radius=S(8)); pygame.draw.rect(SCREEN,WHITE,r,max(2,S(3)),border_radius=S(8)); draw_text("MURO",FONT_S,WHITE,r.center,True)

class ViniciusRock:
    def __init__(self,start,target,target_pos,splash):
        self.pos=pygame.Vector2(start); self.target=target; self.target_pos=pygame.Vector2(target_pos); self.splash=splash; self.radius=S(28); self.life=1.15; self.dead=False
        d=self.target_pos-self.pos; self.vel=d.normalize()*S(780) if d.length_squared()>0 else pygame.Vector2()
    def update(self,dt,game):
        if self.dead:return False
        self.life-=dt; self.pos+=self.vel*dt
        if self.pos.distance_to(self.target_pos)<=S(45) or self.life<=0:
            center=pygame.Vector2(self.target_pos); target=self.target
            if target is not None and not getattr(target,"dead",True): target.damage(min(target.hp,target.max_hp*0.50),game,center)
            old=game.current_damage_kind; game.current_damage_kind="vinicius_anti_titan"
            for e in list(game.enemies):
                if e is not target and not e.dead and e.pos.distance_to(center)<=S(220): e.damage(max(12.0,min(e.max_hp*0.14,self.splash)),game,center,minimal_fx=True)
            game.current_damage_kind=old; game.spawn_particles(center,GRAY,18); game.shake=max(game.shake,S(13)); self.dead=True; return False
        return True
    def draw(self,offset):
        p=self.pos+offset; pygame.draw.circle(SCREEN,(120,125,135),(int(p.x),int(p.y)),self.radius); pygame.draw.circle(SCREEN,DARK,(int(p.x),int(p.y)),self.radius,max(2,S(4)))

class ViniciusTurret:
    NEXT_ID=910000
    COLORS={"heal":GREEN,"random":PURPLE,"shot":RED,"wall":GRAY,"hospital":CYAN,"anti_titan":ORANGE,"ballistic":YELLOW}
    LABELS={"heal":"CURA","random":"ALEATORIA","shot":"DISPARO","wall":"MURALHA","hospital":"HOSPITAL","anti_titan":"ANTI-TITA","ballistic":"BALISTICA"}
    def __init__(self,pos,kind,player,mega=False):
        self.id=ViniciusTurret.NEXT_ID; ViniciusTurret.NEXT_ID+=1; self.pos=pygame.Vector2(pos); self.kind=kind; self.mega=mega; self.dead=False; self.taunt=False; self.owner_player=player
        self.radius=S(72 if mega else 34); self.max_hp=(760 if mega else 125)+player.max_hp*(0.55 if mega else 0.16); self.hp=self.max_hp; self.damage=max(5.0,player.base_damage*(1.45 if mega else 0.72))*player.passive_ally_damage_mult()*getattr(player,"summon_power_mult",1.0); self.cd=random.uniform(0.15,0.8); self.since_hit=99.0
    def take_damage(self,amount,game):
        if self.dead:return
        amount*=max(0.0,1.0-getattr(self.owner_player,"passive_ally_damage_reduction",lambda:0.0)())
        self.hp-=amount
        if self.hp<=0: self.dead=True; game.spawn_particles(self.pos,self.COLORS.get(self.kind,WHITE),18); game.damage_texts.append(DamageText("TORRE DESTRUIDA",pygame.Vector2(self.pos),RED,0.8))
    def heal(self,amount):
        if not self.dead:self.hp=min(self.max_hp,self.hp+amount)
    def update(self,dt,game):
        if self.dead:return False
        self.since_hit=getattr(self,"since_hit",0.0)+dt
        reload_mult=1.25 if getattr(self.owner_player,"hybrid_auto_loader",False) else 1.0
        self.cd-=dt*reload_mult; targets=[e for e in game.enemies if not e.dead]
        if getattr(self.owner_player,"vinicius_auto_maintenance",False) and self.since_hit>=3.0 and self.hp<self.max_hp:
            self.heal(self.max_hp*0.035*dt)
        if self.kind=="heal" and self.cd<=0:
            self.cd=1.8
            if self.pos.distance_to(game.player.pos)<=S(250): game.player.heal(5,game)
            for t in game.vinicius_turrets:
                if t is not self and not t.dead and t.pos.distance_to(self.pos)<=S(250): t.heal(6)
            game.spawn_particles(self.pos,GREEN,5)
        elif self.kind=="random" and self.cd<=0:
            self.cd=4.0; base=random.random()*math.tau
            for i in range(4):
                d=vec_from_angle(base+i*math.tau/4); pr=Projectile(self.pos+d*S(30),d*S(520),self.damage,"player",S(7),PURPLE,1.8,0); pr.kind="vinicius_turret"; pr.origin=pygame.Vector2(self.pos); game.projectiles.append(pr)
        elif self.kind=="shot" and self.cd<=0:
            self.cd=0.75
            if targets:
                target=min(targets,key=lambda e:e.pos.distance_to(game.player.pos)); d=target.pos-self.pos
                if d.length_squared()>0:
                    pr=Projectile(self.pos,d.normalize()*S(640),self.damage,"player",S(7),RED,2.2,0); pr.kind="vinicius_turret"; pr.origin=pygame.Vector2(self.pos); game.projectiles.append(pr)
        elif self.kind=="wall" and self.cd<=0:
            self.cd=5.0
            if len(game.vinicius_walls)<3:
                if targets:
                    target=min(targets,key=lambda e:e.pos.distance_to(game.player.pos)); pos=target.pos+(game.player.pos-target.pos)*0.35
                else: pos=self.pos+vec_from_angle(random.random()*math.tau)*S(180)
                pos.x=clamp(pos.x,S(70),W-S(70)); pos.y=clamp(pos.y,S(220),H-S(390)); game.vinicius_walls.append(ViniciusWall(pos,200))
        elif self.kind=="hospital" and self.cd<=0:
            self.cd=0.95; healed=False
            for t in game.vinicius_turrets:
                if not t.dead and t.hp<t.max_hp: t.heal(16); healed=True; game.spawn_particles(t.pos,CYAN,3)
            if healed: game.damage_texts.append(DamageText("+HP TORRETAS",pygame.Vector2(self.pos),CYAN,0.45))
        elif self.kind=="anti_titan" and self.cd<=0:
            self.cd=5.0
            if targets:
                target=max(targets,key=lambda e:e.max_hp); game.vinicius_rocks.append(ViniciusRock(self.pos,target,target.pos,self.damage*8))
        elif self.kind=="ballistic" and self.cd<=0:
            self.cd=0.16
            if targets:
                target=min(targets,key=lambda e:e.pos.distance_to(self.pos)); d=target.pos-self.pos
                if d.length_squared()>0:
                    pr=Projectile(self.pos,d.normalize()*S(900),self.damage*0.55,"player",S(5),YELLOW,4.0,0); pr.kind="vinicius_ballistic"; pr.origin=pygame.Vector2(self.pos); game.projectiles.append(pr)
        return True
    def draw(self,offset):
        p=self.pos+offset; color=self.COLORS.get(self.kind,WHITE); pygame.draw.circle(SCREEN,color,(int(p.x),int(p.y)),self.radius); pygame.draw.circle(SCREEN,WHITE,(int(p.x),int(p.y)),self.radius,max(2,S(4))); pygame.draw.circle(SCREEN,DARK,(int(p.x),int(p.y)),max(S(8),self.radius//3)); draw_text(self.LABELS.get(self.kind,"TORRE"),FONT_S,DARK if self.kind in ("ballistic","heal") else WHITE,(p.x,p.y),True)
        bw=self.radius*2; y=p.y-self.radius-S(14); pygame.draw.rect(SCREEN,DARK,(p.x-bw/2,y,bw,S(6))); pygame.draw.rect(SCREEN,GREEN,(p.x-bw/2,y,bw*clamp(self.hp/max(1,self.max_hp),0,1),S(6)))

class Enemy:
    NEXT_ID = 1

    def __init__(self, pos, kind, wave, elite=None):
        self.id = Enemy.NEXT_ID
        Enemy.NEXT_ID += 1
        self.pos = pygame.Vector2(pos)
        self.kind = kind
        self.elite = elite
        self.radius = S(28)
        self.flash = 0
        self.shoot_cd = random.uniform(0.4, 1.4)
        self.touch_cd = 0
        self.dead = False
        self.marked = False
        self.blood_marked = False
        self.forge_slow_timer = 0.0
        self.powerup_damage_down_timer = 0.0
        self.coin_value = 2
        self.lira_censor = {"strength":0.0,"speed":0.0,"resistance":0.0,"intelligence":0.0}
        self.lira_domain_stats = set()
        self.lira_fully_censored = False
        self.lira_fully_censored_timer = 0.0

        combat_wave = effective_combat_wave(wave)
        self.combat_wave = combat_wave
        hp_scale, damage_scale, speed_scale = high_wave_scaling(wave)
        self.high_wave_hp_scale = hp_scale
        self.high_wave_damage_scale = damage_scale
        self.high_wave_speed_scale = speed_scale
        base_hp = (26 + combat_wave * 7) * hp_scale
        # V14 WIP 05: velocidade usa a WAVE REAL, nao a wave de combate 7x.
        # Wave 1 -> ~108 base; wave 100 -> ~116; teto total da curva = +12%.
        base_speed = S(108) * enemy_wave_speed_mult(wave)
        self.contact_damage = (7 + combat_wave * 0.7) * damage_scale

        if kind == "chaser":
            self.max_hp = base_hp * 1.15
            self.speed = base_speed * 1.15
            self.color = RED
        elif kind == "shooter":
            self.max_hp = base_hp
            self.speed = base_speed * 0.72
            self.color = ORANGE
        elif kind == "kiter":
            self.max_hp = base_hp * 0.85
            self.speed = base_speed * 1.05
            self.color = YELLOW
        else:  # tank
            self.max_hp = base_hp * 2.4
            self.speed = base_speed * 0.58
            self.radius = S(38)
            self.contact_damage *= 1.45
            self.color = PURPLE
            self.coin_value = 4

        if elite == "frenzy":
            self.speed *= 1.55
            self.color = PINK
            self.coin_value += 2
        elif elite == "giant":
            self.max_hp *= 2.1
            self.radius = int(self.radius * 1.35)
            self.contact_damage *= 1.3
            self.coin_value += 3
        elif elite == "armored":
            self.max_hp *= 1.65
            self.color = (150, 160, 175)
            self.coin_value += 3
        elif elite == "explosive":
            self.color = CYAN
            self.coin_value += 2

        self.hp = self.max_hp

    def lira_stat_level(self, stat, game=None):
        normal=clamp(float(getattr(self,"lira_censor",{}).get(stat,0.0)),0.0,1.0)
        if game is not None and getattr(game,"domain_active",False) and getattr(game.player,"character",None)==LIRA_KEY:
            if stat in getattr(self,"lira_domain_stats",set()):
                normal=max(normal,{"strength":0.70,"speed":0.50,"resistance":1.0,"intelligence":1.0}.get(stat,0.0))
        return normal

    def lira_outgoing_mult(self, game):
        return max(0.10,1.0-self.lira_stat_level("strength",game))

    def apply_lira_censor(self, stat, amount, game):
        if isinstance(self,Boss) or stat not in self.lira_censor:
            return False
        old=self.lira_censor[stat]
        self.lira_censor[stat]=min(0.60,old+max(0.0,amount))
        fully=all(v>0.0 for v in self.lira_censor.values())
        label={"strength":"FORCA","speed":"VELOCIDADE","resistance":"RESISTENCIA","intelligence":"INTELIGENCIA"}[stat]
        if self.lira_censor[stat]>old:
            game.damage_texts.append(DamageText(f"{label} -{int((self.lira_censor[stat]-old)*100)}%",pygame.Vector2(self.pos),LIRA_ACCENT,0.65))
        if fully:
            first_time = self.lira_fully_censored_timer <= 0.0
            self.lira_fully_censored = True
            self.lira_fully_censored_timer = 5.0
            if first_time:
                game.damage_texts.append(DamageText("TOTALMENTE C#NSUR#DO",pygame.Vector2(self.pos),WHITE,0.8))
        return True

    def damage(self, amount, game, source_pos=None, minimal_fx=False):
        if self.dead:
            return
        # POWER UPS 2.0: modificadores que dependem do alvo/fonte entram antes do HP.
        pwr_player = getattr(game, "player", None)
        pwr_source = getattr(game, "current_damage_kind", None) or ""
        if pwr_player is not None:
            projectile_sources = {"projectile","shotgun","dual_pistol","soul_shot","pineapple","pineapple_explosion","vasco_bet","lira_censor","hank_shell","hank_shell_explosion","sukuna_slash","vinicius_bolt","vinicius_turret","vinicius_ballistic","strikada_ball","sans_bone","kevyn_divine_slash","rip_wave","hisoka_card","hisoka_charged_card","hisoka_spider_card","hisoka_domain_card"}
            if getattr(pwr_player, "hybrid_chaotic_ammo", False) and pwr_source in projectile_sources and random.random() < 0.18:
                amount *= 1.60
                if not minimal_fx: game.damage_texts.append(DamageText("CAOS!", pygame.Vector2(self.pos), PURPLE, 0.45))
            if getattr(pwr_player, "lira_torn_page", False) and getattr(self, "lira_fully_censored", False):
                amount *= 1.50
            if getattr(pwr_player, "sukuna_adaptive_cut", False) and pwr_source == "sukuna_slash":
                last = getattr(pwr_player, "sukuna_adaptive_target", None)
                if last == self.id:
                    pwr_player.sukuna_adaptive_hits = min(6, getattr(pwr_player, "sukuna_adaptive_hits", 0) + 1)
                else:
                    pwr_player.sukuna_adaptive_target = self.id; pwr_player.sukuna_adaptive_hits = 0
                amount *= 1.0 + 0.10 * getattr(pwr_player, "sukuna_adaptive_hits", 0)
            if getattr(pwr_player, "strikada_protagonist", False) and pwr_source == "strikada_ball":
                # A contagem e guardada no projetil no loop de colisao; fallback neutro aqui.
                amount *= 1.0 + 0.12 * min(6, getattr(game, "strikada_current_bounces", 0))
        resist_censor=self.lira_stat_level("resistance",game)
        if self.elite=="armored" and resist_censor<0.999:
            amount*=0.72+0.28*resist_censor
        if resist_censor<0.999:
            amount*=1.0+0.25*resist_censor
        amount=max(0.0,float(amount))
        self.hp -= amount
        # V15 BALANCE: so ataques principais explicitamente marcados recarregam Dominio.
        # O valor bruto depende do tipo de ataque e passa pelo divisor global de 5x (~25 ataques).
        domain_raw = getattr(game, "current_domain_charge_raw_override", None)
        game.current_domain_charge_raw_override = None
        if amount > 0.0 and domain_raw is not None and domain_raw > 0.0:
            game.add_domain_charge(domain_raw)
        if hasattr(game, "record_clash_damage"):
            game.record_clash_damage(amount)
        if hasattr(game, "handle_powerup_hit") and amount > 0.0:
            game.handle_powerup_hit(self, amount, source_pos)
        self.flash = 0.08 if minimal_fx else 0.12
        if not minimal_fx:
            game.damage_texts.append(DamageText(str(int(amount)), pygame.Vector2(self.pos), WHITE))
            AUDIO.play("hit", 0.30, 38)
            game.spawn_particles(self.pos, self.color, 7)
            if source_pos is not None:
                knock = self.pos - source_pos
                if knock.length_squared() > 0:
                    self.pos += knock.normalize() * S(10)
        self.marked = self.hp <= self.max_hp * 0.18 and self.hp > 0
        if self.hp <= 0:
            self.die(game)

    def die(self, game):
        if self.dead:
            return
        self.dead = True
        game.kills += 1
        game.combo = min(50, game.combo + 1)
        game.combo_timer = 3.0
        if game.combo >= 50:
            game.unlock_achievement("combo_50")
        reward_mult = difficulty_cfg(getattr(game, "difficulty", "easy"))["reward"] if game.mode == "arena" else 1.0
        reward = int(self.coin_value * game.coin_multiplier * reward_mult * (1.0 + 0.05 * SAVE.get("coin_level", 0)) * max(0.10,1.0+getattr(game.player,"passive_coin_bonus",0.0)))
        game.run_coins += reward
        game.score += int(100 * (1 + game.combo * 0.08))
        AUDIO.play("enemy_die", 0.38, 45)
        game.spawn_particles(self.pos, self.color, 16)
        game.shake = max(game.shake, S(7))
        game.on_enemy_killed(self)

        if self.elite == "explosive":
            for i in range(8):
                v = vec_from_angle(i * math.tau / 8) * S(260)
                game.projectiles.append(Projectile(self.pos, v, 6, "enemy", S(9), CYAN))

        # Chuva de Orbes garante uma orb principal em elite. No EXTINCAO nunca nasce cura.
        extinction = getattr(game,"game_mode","normal") == "extinction"
        guaranteed = self.elite and game.player.orb_rain
        if guaranteed:
            game.drops.append(Drop(self.pos, "stamina" if extinction else random.choice(["heal", "stamina"])))

        bonus_each = game.player.drop_bonus * 0.5
        heal_chance = 0.0 if extinction else min(0.32, 0.14 + bonus_each)
        stamina_chance = min(0.38 if extinction else 0.32, 0.18 + bonus_each if extinction else 0.14 + bonus_each)
        roll = random.random()
        if roll < heal_chance:
            game.drops.append(Drop(self.pos, "heal"))
        elif roll < heal_chance + stamina_chance:
            game.drops.append(Drop(self.pos, "stamina"))
        elif roll < heal_chance + stamina_chance + 0.05:
            game.drops.append(Drop(self.pos, "shield"))
        elif roll < heal_chance + stamina_chance + 0.10:
            game.drops.append(Drop(self.pos, "haste"))
        elif roll < heal_chance + stamina_chance + 0.25:
            game.drops.append(Drop(self.pos, "coin"))

        # Materiais da Forja sao progresso persistente; Beta nao gera loot persistente.
        if hasattr(game, "roll_forge_drop"):
            game.roll_forge_drop(self)

    def update(self, dt, game):
        if self.dead:
            return
        self.flash = max(0, self.flash - dt)
        self.hisoka_stun_timer=max(0.0,getattr(self,"hisoka_stun_timer",0.0)-dt)
        if self.hisoka_stun_timer>0.0:
            return
        self.forge_slow_timer = max(0.0, getattr(self, "forge_slow_timer", 0.0) - dt)
        self.powerup_damage_down_timer = max(0.0, getattr(self, "powerup_damage_down_timer", 0.0)-dt)
        self.lira_fully_censored_timer = max(0.0, getattr(self, "lira_fully_censored_timer", 0.0) - dt)
        self.lira_fully_censored = self.lira_fully_censored_timer > 0.0
        lira_speed=self.lira_stat_level("speed",game)
        move_speed=self.speed*(0.55 if self.forge_slow_timer>0 else 1.0)*max(0.20,1.0-lira_speed)
        lira_intel=self.lira_stat_level("intelligence",game)
        lira_power=self.lira_outgoing_mult(game) * (0.65 if self.powerup_damage_down_timer>0 else 1.0)
        self.shoot_cd -= dt
        self.touch_cd -= dt

        target_entity = game.get_enemy_target(self.pos)
        to_player = target_entity.pos - self.pos
        dist = max(1, to_player.length())
        direction=to_player/dist
        if lira_intel>=0.999:
            away=self.pos-game.player.pos
            direction=away.normalize() if away.length_squared()>0 else vec_from_angle(random.random()*math.tau)
        elif lira_intel>0 and random.random()<lira_intel:
            direction=vec_from_angle(random.random()*math.tau)

        hank_trapped = getattr(game, "hank_domain_active", False) and self.id in getattr(game, "hank_domain_trapped_ids", set())
        if hank_trapped:
            away = self.pos - game.player.pos
            if away.length_squared() <= 0:
                away = vec_from_angle(random.random()*math.tau)
            direction = away.normalize()

        if self.kind == "chaser" or self.kind == "tank":
            self.pos += direction * move_speed * dt
        elif self.kind == "shooter":
            if dist > S(470):
                self.pos += direction * move_speed * dt
            elif dist < S(300):
                self.pos -= direction * move_speed * dt
            if self.shoot_cd <= 0 and self.lira_fully_censored_timer <= 0.0:
                dcfg = difficulty_cfg(getattr(game, "difficulty", "easy")) if game.mode == "arena" else DIFFICULTIES["easy"]
                cw = effective_combat_wave(game.wave)
                speed = S(300 + cw * 5) * min(1.45, 1.0 + (dcfg["ai"]-1.0)*0.28)
                game.projectiles.append(Projectile(self.pos, direction * speed, (7 + cw * 0.55) * self.high_wave_damage_scale * dcfg["damage"] * lira_power, "enemy"))
                self.shoot_cd = max(0.22, (max(0.38, 1.45 - cw * 0.02)) / dcfg["ai"])
        elif self.kind == "kiter":
            tangent = pygame.Vector2(-direction.y, direction.x)
            if dist < S(360):
                move = -direction * 0.8 + tangent * 0.65
            else:
                move = direction * 0.35 + tangent * 0.8
            if move.length_squared() > 0:
                self.pos += move.normalize() * move_speed * dt
            if self.shoot_cd <= 0 and self.lira_fully_censored_timer <= 0.0:
                for off in (-0.12, 0.12):
                    a = math.atan2(direction.y, direction.x) + off
                    dcfg = difficulty_cfg(getattr(game, "difficulty", "easy")) if game.mode == "arena" else DIFFICULTIES["easy"]
                    shot_speed = S(330) * min(1.45, 1.0 + (dcfg["ai"]-1.0)*0.28)
                    cw = effective_combat_wave(game.wave)
                    game.projectiles.append(Projectile(self.pos, vec_from_angle(a) * shot_speed, (5 + cw * 0.45) * self.high_wave_damage_scale * dcfg["damage"] * lira_power, "enemy", S(8), YELLOW))
                dcfg = difficulty_cfg(getattr(game, "difficulty", "easy")) if game.mode == "arena" else DIFFICULTIES["easy"]
                self.shoot_cd = 1.8 / dcfg["ai"]

        # contato: amigos do Ruan podem realmente proteger o jogador e receber golpes.
        if dist < self.radius + target_entity.radius and self.touch_cd <= 0 and self.lira_fully_censored_timer <= 0.0:
            target_entity.take_damage(self.contact_damage*lira_power, game)
            self.touch_cd = 0.75
            if target_entity is game.player and direction.length_squared() > 0:
                game.player.pos += direction * S(28) * getattr(self,"difficulty_force",1.0)

        self.pos.x = clamp(self.pos.x, self.radius, W - self.radius)
        self.pos.y = clamp(self.pos.y, S(165) + self.radius, H - S(335) - self.radius)
        if hank_trapped and getattr(game, "domain_active", False):
            rel = self.pos - game.domain_center
            dist_dom = rel.length()
            limit = max(0, game.domain_radius - self.radius - S(4))
            if dist_dom > limit and dist_dom > 0:
                self.pos = game.domain_center + rel.normalize() * limit

    def draw(self, offset):
        p = self.pos + offset
        color = WHITE if self.flash > 0 else self.color
        if getattr(self,"lira_fully_censored",False):
            img=censured_form_surface(max(S(72),self.radius*2 + S(28)))
            if img is not None:
                SCREEN.blit(img,img.get_rect(center=(int(p.x),int(p.y))))
            else:
                r=pygame.Rect(int(p.x-self.radius),int(p.y-self.radius*0.55),self.radius*2,max(S(18),int(self.radius*1.1)))
                pygame.draw.rect(SCREEN,DARK,r,border_radius=max(1,S(4)))
                pygame.draw.rect(SCREEN,WHITE,r,max(1,S(2)),border_radius=max(1,S(4)))
                draw_text("C#NSUR#",FONT_S,WHITE,r.center,True)
        else:
            pygame.draw.circle(SCREEN,color,(int(p.x),int(p.y)),self.radius)
            pygame.draw.circle(SCREEN,DARK,(int(p.x),int(p.y)),max(2,self.radius//3),S(3))
        # barra hp
        bw = self.radius * 2
        x = p.x - bw / 2
        y = p.y - self.radius - S(15)
        pygame.draw.rect(SCREEN, DARK, (x, y, bw, S(7)))
        pygame.draw.rect(SCREEN, GREEN, (x, y, bw * clamp(self.hp / self.max_hp, 0, 1), S(7)))
        if self.elite:
            pygame.draw.circle(SCREEN, WHITE, (int(p.x), int(p.y)), self.radius + S(5), S(3))
        if self.marked:
            draw_text("EXEC!", FONT_S, YELLOW, (p.x, p.y - self.radius - S(45)), True)
        if self.blood_marked:
            pygame.draw.circle(SCREEN, RED, (int(p.x), int(p.y)), self.radius + S(10), S(4))
        if getattr(self,"lira_fully_censored",False):
            draw_text(f"MUDO {self.lira_fully_censored_timer:.1f}s", FONT_S, LIRA_ACCENT, (p.x, p.y + self.radius + S(18)), True)
            draw_text("PRESA", FONT_S, RED, (p.x, p.y + self.radius + S(44)), True)


class GlonkMinion(Enemy):
    """Pequeno Glonk invocado por GLONK, O ULTIMO. Simples, rapido e irritante."""
    def __init__(self, pos, wave, parent=None):
        super().__init__(pos, "chaser", max(1, wave), None)
        self.kind = "glonk_minion"
        self.parent = parent
        self.color = GREEN
        self.radius = S(18)
        self.max_hp = max(12.0, self.max_hp * 0.28)
        self.hp = self.max_hp
        self.speed = max(S(145), min(S(230), self.speed * 1.12))
        self.contact_damage = max(4.0, self.contact_damage * 0.45)
        self.coin_value = 0
        self.elite = None

    def draw(self, offset):
        p = self.pos + offset
        pygame.draw.circle(SCREEN, GREEN, (int(p.x), int(p.y)), self.radius)
        pygame.draw.circle(SCREEN, DARK, (int(p.x), int(p.y)), self.radius, max(1, S(2)))
        pygame.draw.circle(SCREEN, WHITE, (int(p.x-S(5)), int(p.y-S(4))), max(1,S(2)))
        pygame.draw.circle(SCREEN, WHITE, (int(p.x+S(6)), int(p.y-S(2))), max(1,S(2)))
        draw_text("glonk", FONT_S, GREEN, (p.x, p.y-self.radius-S(22)), True)


class GlonkEnemy(Enemy):
    """Inimigo raro: foge durante a wave e vira GLONK, O ULTIMO se for deixado por ultimo."""
    def __init__(self, pos, wave, target_hp=None, target_speed=None, training=False):
        super().__init__(pos, "chaser", wave, None)
        self.kind = "glonk_fugitive"
        self.color = GREEN
        self.radius = S(34)
        if target_hp is not None:
            self.max_hp = max(4.0, float(target_hp))
            self.hp = self.max_hp
        if target_speed is not None:
            self.speed = max(S(175), float(target_speed))
        else:
            self.speed = max(S(185), self.speed * 1.55)
        self.contact_damage = 0.0
        self.coin_value = 16
        self.phase = "flee"  # flee -> transform -> boss
        self.transform_timer = 0.0
        self.is_glonk_boss = False
        self.flee_rethink = 0.0
        self.flee_target = pygame.Vector2(self.pos)
        self.boss_lunge_cd = 0.0
        self.boss_touch_cd = 0.0
        self.aura_phase = random.random() * math.tau
        self.training = training
        self.is_decoy = False
        self.hunt_level = 1
        self.hunt_dash_cd = random.uniform(1.7,2.8)
        self.hunt_swap_cd = random.uniform(3.2,5.0)
        # Kit exclusivo de GLONK, O ULTIMO.
        self.boss_tongue_cd = random.uniform(1.5, 2.4)
        self.boss_summon_cd = random.uniform(4.8, 6.4)
        self.boss_cry_cd = 3.8
        self.boss_miss_timer = 0.0
        self.boss_cry_count = 0
        self.boss_tantrum_cd = 0.0
        self.tantrum_fx = 0.0
        self.tongue_fx = 0.0
        self.tongue_dir = pygame.Vector2(1,0)
        self.cry_fx = 0.0
        self.death_sequence = False
        self.death_timer = 0.0
        self.death_radius = S(520)

    def damage(self, amount, game, source_pos=None, minimal_fx=False):
        # As cutscenes de transformacao e morte sao invulneraveis.
        if self.phase == "transform" or self.death_sequence:
            if not minimal_fx:
                game.damage_texts.append(DamageText("...", pygame.Vector2(self.pos), GREEN, 0.35))
            return
        super().damage(amount, game, source_pos, minimal_fx)

    def _other_enemies(self, game):
        return [e for e in game.enemies if e is not self and not getattr(e, "dead", False)]

    @staticmethod
    def _point_segment_distance(point, a, b):
        ab = b - a
        den = ab.length_squared()
        if den <= 0.001:
            return point.distance_to(a)
        t = clamp((point-a).dot(ab)/den, 0.0, 1.0)
        return point.distance_to(a + ab*t)

    def _safe_boss_action(self, label, fn, game):
        """Um erro isolado num ataque do Glonk nao deve fechar o APK inteiro."""
        try:
            fn(game)
            return True
        except Exception as exc:
            # Evita spam de efeitos/recursao e deixa a luta continuar.
            self.boss_tongue_cd=max(self.boss_tongue_cd,1.2)
            self.boss_summon_cd=max(self.boss_summon_cd,2.0)
            self.boss_cry_cd=max(self.boss_cry_cd,1.5)
            try:
                game.damage_texts.append(DamageText("GLONK TROPECOU",pygame.Vector2(self.pos),GREEN,0.45))
            except Exception:
                pass
            return False

    def choose_flee_target(self, game):
        """Escolhe uma area que combine distancia, espaco livre, cobertura e rota de fuga."""
        p = game.player.pos
        min_x, max_x = self.radius + S(12), W - self.radius - S(12)
        min_y, max_y = S(175) + self.radius, H - S(345) - self.radius
        arena_diag = max(1.0, math.hypot(max_x-min_x, max_y-min_y))
        others = self._other_enemies(game)
        best_score = -10**9
        best = pygame.Vector2(self.pos)
        step = S(260)
        away = self.pos - p
        away_angle = math.atan2(away.y, away.x) if away.length_squared() else 0.0
        angles = [away_angle + off for off in (0, -0.35, 0.35, -0.75, 0.75, -1.25, 1.25, math.pi)]
        angles += [i*math.tau/12 for i in range(12)]
        for ang in angles:
            raw = self.pos + vec_from_angle(ang) * step
            cand = pygame.Vector2(clamp(raw.x,min_x,max_x), clamp(raw.y,min_y,max_y))
            dist_score = cand.distance_to(p) / arena_diag
            wall_clear = min(cand.x-min_x, max_x-cand.x, cand.y-min_y, max_y-cand.y)
            wall_score = clamp(wall_clear/max(S(120),min(W,H)*0.20),0,1)
            cover = 0
            for e in others:
                ep = pygame.Vector2(e.pos)
                if ep.distance_to(p) < cand.distance_to(p) and self._point_segment_distance(ep,p,cand) <= S(105):
                    cover += 1
            cover_score = min(1.0, cover/5.0)
            exits = 0
            for j in range(8):
                q = cand + vec_from_angle(j*math.tau/8)*S(100)
                if min_x < q.x < max_x and min_y < q.y < max_y:
                    exits += 1
            route_score = exits/8.0
            danger_penalty = max(0.0, 1.0 - cand.distance_to(p)/max(S(350),1))
            score = dist_score*3.2 + wall_score*0.85 + cover_score*1.05 + route_score*0.70 - danger_penalty*2.0
            if score > best_score:
                best_score, best = score, cand
        self.flee_target = best

    def begin_transform(self, game):
        if self.phase != "flee" or self.dead:
            return
        self.phase = "transform"
        self.transform_timer = 2.35
        self.speed = 0.0
        self.contact_damage = 0.0
        self.vel = pygame.Vector2() if hasattr(self,"vel") else None
        game.glonk_music_cut_timer = max(game.glonk_music_cut_timer, 2.35)
        game.glonk_event_timer = 2.35
        game.glonk_event_stage = "trapped"
        game.shake = max(game.shake, S(7))
        AUDIO.play("glonk", 1.0, 100)

    def finish_transform(self, game):
        self.phase = "boss"
        self.is_glonk_boss = True
        self.radius = S(62)
        old_max = self.max_hp
        self.max_hp *= 1.35
        self.hp = min(self.max_hp, max(self.hp + (self.max_hp-old_max), self.max_hp*0.55))
        player_speed = max(S(230), min(S(390), getattr(game.player,"base_speed",S(290))*1.05))
        self.speed = player_speed
        self.contact_damage = max(18.0, game.player.max_hp*0.18)
        self.coin_value = 90
        self.boss_touch_cd = 0.0
        self.boss_lunge_cd = 1.0
        self.boss_tongue_cd = 1.6
        self.boss_summon_cd = 4.0
        self.boss_cry_cd = 3.0
        self.boss_miss_timer = 0.0
        game.glonk_event_stage = "boss"
        game.glonk_event_timer = 2.4
        game.glonk_boss_intro_timer = 2.4
        game.glonk_music_cut_timer = 0.0
        game.shake = max(game.shake, S(18))
        if getattr(game,"game_mode","normal")=="glonk_hunt":
            game.hunt_glonk_transform_count += 1
            n=game.hunt_glonk_transform_count
            self.max_hp*=1.0+0.18*max(0,n-1); self.hp=self.max_hp
            self.speed*=min(1.50,1.0+0.07*max(0,n-1)); self.contact_damage*=1.0+0.10*max(0,n-1)
        if not SAVE.get("glonk_last_discovered", False):
            SAVE["glonk_last_discovered"] = True
            save_data(SAVE)
        AUDIO.play("boss", 1.0, 100)

    def _boss_tongue_attack(self, game):
        """Lingua do Glonk: mesmo estilo do ataque do Glonk 100%, mas como chicote longo."""
        delta = game.player.pos - self.pos
        if delta.length_squared() <= 0.001:
            delta = pygame.Vector2(1,0)
        d = delta.normalize()
        self.tongue_dir = pygame.Vector2(d)
        self.tongue_fx = 0.24
        reach = S(355)
        width = S(28)
        end = self.pos + d * reach
        if self._point_segment_distance(game.player.pos, self.pos, end) <= width + game.player.radius:
            hit = game.player.take_damage(max(10.0, game.player.max_hp*0.12), game)
            if hit is not False:
                self.boss_miss_timer = 0.0
                self.boss_cry_count = 0
            game.damage_texts.append(DamageText("LAMBIDA!", pygame.Vector2(game.player.pos), GREEN, 0.65))
        else:
            self.boss_miss_timer += 0.8
        game.shake = max(game.shake, S(5))
        AUDIO.play("hit", 0.35, 80)

    def _boss_cry(self, game):
        """Se o Glonk passa tempo demais sem acertar, ele literalmente chora projeteis gigantes."""
        self.cry_fx = 0.85
        self.boss_cry_count += 1
        game.damage_texts.append(DamageText("BUAAAAAAAA!", pygame.Vector2(self.pos), CYAN, 1.0))
        aim = game.player.pos - self.pos
        base = math.atan2(aim.y, aim.x) if aim.length_squared() else 0.0
        for off in (-0.42, -0.21, 0.0, 0.21, 0.42):
            d = vec_from_angle(base + off)
            pr = Projectile(self.pos + d*(self.radius+S(10)), d*S(245), max(7.0, game.player.max_hp*0.075), "enemy", S(19), CYAN, 4.0, 0)
            pr.kind = "glonk_tear"
            game.projectiles.append(pr)
        for side in (-1,1):
            d = vec_from_angle(base + side*1.05)
            pr = Projectile(self.pos, d*S(185), max(5.0, game.player.max_hp*0.05), "enemy", S(16), BLUE, 3.5, 0)
            pr.kind = "glonk_tear"
            game.projectiles.append(pr)
        game.spawn_particles(self.pos, CYAN, 8)
        game.shake = max(game.shake, S(7))

    def _boss_tantrum(self, game):
        """BIRRA: depois de chorar demais, Glonk perde a paciencia e da um dash desesperado."""
        delta = game.player.pos - self.pos
        if delta.length_squared() <= 0.001:
            return
        d = delta.normalize()
        start = pygame.Vector2(self.pos)
        dash_len = min(S(300), max(S(150), delta.length()*0.72))
        self.pos += d * dash_len
        self.pos.x = clamp(self.pos.x, self.radius, W-self.radius)
        self.pos.y = clamp(self.pos.y, S(175)+self.radius, H-S(345)-self.radius)
        self.tantrum_fx = 0.35
        game.damage_texts.append(DamageText("BIRRA!", pygame.Vector2(self.pos), RED, 0.9))
        game.spawn_particles(start, GREEN, 10); game.spawn_particles(self.pos, GREEN, 14)
        if self._point_segment_distance(game.player.pos, start, self.pos) <= self.radius + game.player.radius + S(18):
            hit = game.player.take_damage(max(12.0, game.player.max_hp*0.16), game)
            if hit is not False:
                self.boss_miss_timer = 0.0
        game.shake = max(game.shake, S(12))

    def _boss_summon_glonks(self, game):
        alive = [e for e in game.enemies if isinstance(e, GlonkMinion) and not e.dead]
        slots = max(0, 5-len(alive))
        count = min(slots, random.choice([1,2,2,3]))
        if count <= 0:
            return
        for i in range(count):
            a = i*math.tau/max(1,count) + random.uniform(-0.35,0.35)
            pos = self.pos + vec_from_angle(a)*S(85)
            pos.x = clamp(pos.x, S(30), W-S(30)); pos.y = clamp(pos.y, S(190), H-S(360))
            game.enemies.append(GlonkMinion(pos, self.wave, self))
        game.damage_texts.append(DamageText("MAIS GLONKS!", pygame.Vector2(self.pos), GREEN, 0.8))
        game.spawn_particles(self.pos, GREEN, 12)

    def die(self, game):
        # GLONK, O ULTIMO nao simplesmente cai: ele avisa por 2s e explode.
        if self.phase == "boss" and not self.death_sequence:
            self.death_sequence = True
            self.death_timer = 2.0
            self.hp = 1.0
            self.speed = 0.0
            self.contact_damage = 0.0
            self.boss_tongue_cd = 999.0
            self.boss_summon_cd = 999.0
            game.damage_texts.append(DamageText("...GLONK?", pygame.Vector2(self.pos), GREEN, 1.2))
            game.shake = max(game.shake, S(8))
            return
        if self.death_sequence:
            return
        super().die(game)

    def _finish_death_explosion(self, game):
        radius = self.death_radius
        game.shake = max(game.shake, S(32))
        game.spawn_particles(self.pos, GREEN, 24)
        game.spawn_particles(self.pos, WHITE, 10)
        # A explosao e evitavel saindo da area; dentro dela tira 50% do HP MAXIMO.
        if self.pos.distance_to(game.player.pos) <= radius + game.player.radius:
            if SAVE.get("cheat_immortal", False):
                game.damage_texts.append(DamageText("IMORTAL", pygame.Vector2(game.player.pos), YELLOW, 0.65))
            elif game.player.invuln > 0 or game.player.dash_time > 0:
                game.damage_texts.append(DamageText("ESCAPOU!", pygame.Vector2(game.player.pos), WHITE, 0.75))
            else:
                dmg = game.player.max_hp * 0.50
                game.player.hp -= dmg
                if getattr(game,"game_mode","normal") == "extinction":
                    cap = getattr(game,"extinction_hp_cap",None)
                    game.extinction_hp_cap = game.player.hp if cap is None else min(cap, game.player.hp)
                game.damage_texts.append(DamageText("-50% HP", pygame.Vector2(game.player.pos), RED, 1.0))
                AUDIO.play("hurt", 1.0, 100)
        # Pequenos Glonks somem junto para a wave nao ficar presa.
        for e in game.enemies:
            if isinstance(e, GlonkMinion) and not e.dead:
                e.dead = True
                game.spawn_particles(e.pos, GREEN, 6)
        self.hp = 0.0
        self.death_sequence = False
        super().die(game)

    def update(self, dt, game):
        if self.dead:
            return
        self.flash = max(0, self.flash-dt)
        self.aura_phase += dt*5.0
        self.tongue_fx = max(0.0, self.tongue_fx-dt)
        self.cry_fx = max(0.0, self.cry_fx-dt)
        self.tantrum_fx = max(0.0, self.tantrum_fx-dt)
        if self.death_sequence:
            self.death_timer -= dt
            game.shake = max(game.shake, S(4) + int(S(9)*(1.0-clamp(self.death_timer/2.0,0,1))))
            if random.random() < min(0.45, dt*12):
                game.spawn_particles(self.pos + pygame.Vector2(random.uniform(-self.radius,self.radius),random.uniform(-self.radius,self.radius)), GREEN, 2)
            if self.death_timer <= 0:
                try:
                    self._finish_death_explosion(game)
                except Exception:
                    # Se o FX final falhar, encerra o boss sem derrubar o jogo.
                    self.hp=0.0; self.death_sequence=False; super().die(game)
            return
        if self.phase == "flee":
            if not self._other_enemies(game):
                self.begin_transform(game)
                return
            if getattr(game,"game_mode","normal")=="glonk_hunt":
                self.hunt_dash_cd-=dt; self.hunt_swap_cd-=dt
                if self.hunt_level>=3 and self.hunt_dash_cd<=0:
                    away=self.pos-game.player.pos
                    if away.length_squared()>0: self.pos += away.normalize()*S(105)
                    self.hunt_dash_cd=max(0.85,2.6-0.12*self.hunt_level)
                    game.spawn_particles(self.pos,GREEN,6)
                if self.hunt_level>=7 and self.hunt_swap_cd<=0:
                    opts=[e for e in self._other_enemies(game) if not isinstance(e,GlonkEnemy)]
                    if opts:
                        other=random.choice(opts); old=pygame.Vector2(self.pos); self.pos=pygame.Vector2(other.pos); other.pos=old
                        game.damage_texts.append(DamageText("TROCOU!",pygame.Vector2(self.pos),GREEN,0.55))
                    self.hunt_swap_cd=max(1.8,5.0-0.20*self.hunt_level)
            self.flee_rethink -= dt
            if self.flee_rethink <= 0:
                self.choose_flee_target(game)
                self.flee_rethink = 0.16
            delta = self.flee_target - self.pos
            if delta.length_squared() > S(12)**2:
                d = delta.normalize()
                self.pos += d * self.speed * dt
            self.pos.x = clamp(self.pos.x, self.radius, W-self.radius)
            self.pos.y = clamp(self.pos.y, S(175)+self.radius, H-S(345)-self.radius)
            return
        if self.phase == "transform":
            self.transform_timer -= dt
            game.shake = max(game.shake, S(4) + int(S(5)*(1.0-clamp(self.transform_timer/2.35,0,1))))
            if self.transform_timer <= 1.15 and game.glonk_event_stage == "trapped":
                game.glonk_event_stage = "stopped"
                game.glonk_event_timer = max(game.glonk_event_timer, 1.15)
            if self.transform_timer <= 0:
                self.finish_transform(game)
            return

        # GLONK, O ULTIMO: persegue, usa lingua, invoca mini-Glonks e chora se falhar demais.
        self.boss_touch_cd = max(0.0, self.boss_touch_cd-dt)
        self.boss_lunge_cd -= dt
        self.boss_tongue_cd -= dt
        self.boss_summon_cd -= dt
        self.boss_cry_cd -= dt
        self.boss_tantrum_cd = max(0.0, self.boss_tantrum_cd-dt)
        self.boss_miss_timer += dt
        delta = game.player.pos - self.pos
        dist = max(1.0, delta.length())
        d = delta/dist
        move_mult = 1.15
        if self.boss_lunge_cd <= 0:
            move_mult = 2.15 + min(0.75, self.boss_miss_timer*0.06)
            self.boss_lunge_cd = random.uniform(1.05,1.55)
        self.pos += d * self.speed * move_mult * dt
        game.shake = max(game.shake, S(2))

        if self.boss_tongue_cd <= 0 and dist <= S(430):
            self._safe_boss_action("tongue", self._boss_tongue_attack, game)
            self.boss_tongue_cd = random.uniform(2.25,3.15)
        if self.boss_summon_cd <= 0:
            self._safe_boss_action("summon", self._boss_summon_glonks, game)
            self.boss_summon_cd = random.uniform(5.3,7.0)
        if self.boss_miss_timer >= 4.6 and self.boss_cry_cd <= 0:
            self._safe_boss_action("cry", self._boss_cry, game)
            self.boss_cry_cd = random.uniform(3.4,4.4)
            self.boss_miss_timer = 1.2
            if self.boss_cry_count >= 2 and self.boss_tantrum_cd <= 0:
                self._safe_boss_action("tantrum", self._boss_tantrum, game)
                self.boss_tantrum_cd = 8.0
                self.boss_cry_count = 0

        if dist <= self.radius + game.player.radius + S(5) and self.boss_touch_cd <= 0:
            hit = game.player.take_damage(max(self.contact_damage, game.player.max_hp*0.18), game)
            game.player.stamina = max(0.0, game.player.stamina - game.player.max_stamina*0.08)
            game.player.stamina_regen_delay = max(game.player.stamina_regen_delay,0.75)
            game.damage_texts.append(DamageText("AGORA CORRA VOCE.", pygame.Vector2(game.player.pos), GREEN, 0.75))
            if hit is not False:
                self.boss_miss_timer = 0.0
                self.boss_cry_count = 0
            self.boss_touch_cd = 0.48
        self.pos.x = clamp(self.pos.x, self.radius, W-self.radius)
        self.pos.y = clamp(self.pos.y, S(175)+self.radius, H-S(345)-self.radius)

    def draw(self, offset):
        p = self.pos + offset
        color = WHITE if self.flash > 0 else GREEN
        if self.phase == "boss" or self.death_sequence:
            aura = self.radius + S(13) + int(S(5)*(0.5+0.5*math.sin(self.aura_phase)))
            if self.death_sequence:
                ratio = 1.0-clamp(self.death_timer/2.0,0,1)
                aura += int(S(90)*ratio)
            pygame.draw.circle(SCREEN, (45,255,95), (int(p.x),int(p.y)), aura, max(2,S(5)))
            pygame.draw.circle(SCREEN, (20,120,50), (int(p.x),int(p.y)), aura+S(10), max(1,S(3)))
        pygame.draw.circle(SCREEN, color, (int(p.x),int(p.y)), self.radius)
        pygame.draw.circle(SCREEN, DARK, (int(p.x),int(p.y)), self.radius, max(2,S(3)))
        eye_col = WHITE if (self.phase != "boss" and not self.death_sequence) else YELLOW
        eye_y = int(p.y-S(8))
        pygame.draw.circle(SCREEN, eye_col, (int(p.x-S(10)), eye_y), max(2,S(4)))
        pygame.draw.circle(SCREEN, eye_col, (int(p.x+S(10)), eye_y), max(2,S(4)))
        name = "GLONK, O ULTIMO" if (self.phase == "boss" or self.death_sequence) else "GLONK"
        draw_text(name, FONT_M if (self.phase=="boss" or self.death_sequence) else FONT_S, GREEN, (p.x,p.y-self.radius-S(58)), True)
        if self.tongue_fx > 0:
            d = self.tongue_dir if self.tongue_dir.length_squared() else pygame.Vector2(1,0)
            end = p + d.normalize()*S(355)
            pygame.draw.line(SCREEN, GREEN, p, end, max(S(14),S(21)))
            pygame.draw.circle(SCREEN, WHITE, (int(end.x),int(end.y)), S(14), max(1,S(3)))
        if self.tantrum_fx > 0:
            pygame.draw.circle(SCREEN, RED, (int(p.x),int(p.y)), self.radius+S(24), max(2,S(5)))
        if self.cry_fx > 0:
            for sx in (-1,1):
                start = pygame.Vector2(p.x+sx*S(12), p.y+S(2))
                end = start + pygame.Vector2(sx*S(5), S(34))
                pygame.draw.line(SCREEN, CYAN, start, end, max(S(6),S(9)))
                pygame.draw.circle(SCREEN, CYAN, (int(end.x),int(end.y)), S(8))
        if self.death_sequence:
            ratio = 1.0-clamp(self.death_timer/2.0,0,1)
            warn_r = int(self.death_radius * (0.45 + 0.55*ratio))
            pygame.draw.circle(SCREEN, GREEN, (int(p.x),int(p.y)), warn_r, max(2,S(7)))
            draw_text("SAIA DA AREA!", FONT_M, RED, (p.x,p.y+self.radius+S(64)), True)
        bw=self.radius*2.2; x=p.x-bw/2; y=p.y-self.radius-S(22)
        pygame.draw.rect(SCREEN,DARK,(x,y,bw,S(8)))
        pygame.draw.rect(SCREEN,GREEN,(x,y,bw*clamp(self.hp/max(1,self.max_hp),0,1),S(8)))


class TrainingDummy(Enemy):
    """Bekita da Zona AFK: alvo imortal, parado e completamente bobinho."""
    def __init__(self, pos, wave=1):
        super().__init__(pos, "tank", wave, None)
        self.max_hp = 260
        self.hp = self.max_hp
        self.radius = S(42)
        self.speed = 0
        self.contact_damage = 0
        self.color = PINK
        self.coin_value = 0
        self.goofy_phase = random.random()*math.tau

    def update(self, dt, game):
        self.flash = max(0, self.flash - dt)
        self.marked = self.hp <= self.max_hp * 0.18 and self.hp > 0
        self.goofy_phase += dt*2.2

    def die(self, game):
        self.dead = False
        self.hp = self.max_hp
        self.marked = False
        self.blood_marked = False
        game.combo = min(50, game.combo + 1)
        game.combo_timer = 3.0
        game.on_enemy_killed(self)
        game.spawn_particles(self.pos, PINK, 12)
        game.damage_texts.append(DamageText("BEKITA: hehe", pygame.Vector2(self.pos), PINK))

    def draw(self, offset):
        p=self.pos+offset
        wob=int(math.sin(self.goofy_phase)*S(3))
        body=(int(p.x),int(p.y+wob))
        pygame.draw.circle(SCREEN,PINK,body,self.radius)
        pygame.draw.circle(SCREEN,WHITE,body,self.radius,max(2,S(3)))
        # Cara deliberadamente boba: olhos tortos e sorriso simples.
        eye_y=body[1]-S(8)
        pygame.draw.circle(SCREEN,WHITE,(body[0]-S(14),eye_y),S(7))
        pygame.draw.circle(SCREEN,WHITE,(body[0]+S(16),eye_y+S(3)),S(7))
        pygame.draw.circle(SCREEN,DARK,(body[0]-S(12),eye_y+S(2)),S(3))
        pygame.draw.circle(SCREEN,DARK,(body[0]+S(18),eye_y+S(1)),S(3))
        pygame.draw.arc(SCREEN,DARK,(body[0]-S(18),body[1]-S(1),S(36),S(28)),0.12*math.pi,0.88*math.pi,max(2,S(3)))
        draw_text("BEKITA", FONT_S, PINK, (p.x, p.y + self.radius + S(24)), True)
        draw_text("hehe", FONT_S, WHITE, (p.x, p.y + self.radius + S(50)), True)


class Boss(Enemy):
    def __init__(self, pos, wave):
        super().__init__(pos, "tank", wave, None)
        self.radius = S(72)
        combat_wave = effective_combat_wave(wave)
        hp_scale, damage_scale, speed_scale = high_wave_scaling(wave)
        self.boss_damage_scale = damage_scale
        self.max_hp = (700 + combat_wave * 95) * hp_scale
        self.hp = self.max_hp
        # Bosses mantem pressao por IA/dano/ataques, nao por velocidade absurda.
        self.speed = S(88) * enemy_wave_speed_mult(wave)
        self.coin_value = 55
        self.wave = combat_wave
        self.display_wave = wave
        cfg = BOSS_VARIANTS[((wave // 5) - 1) % len(BOSS_VARIANTS)]
        self.variant = cfg["key"]
        self.name = cfg["name"]
        self.color = cfg["color"]
        self.domain_name = cfg["domain"]
        self.domain_desc = cfg["domain_desc"]
        self.burst_cd = 1.0
        self.charge_cd = 3.0
        self.charging = 0
        self.charge_dir = pygame.Vector2()
        self.domain_cd = 4.8
        self.domain_active = False
        self.domain_timer = 0.0
        self.domain_radius = S(480)
        self.domain_center = pygame.Vector2(self.pos)
        self.domain_tick = 0.0
        self.clash_buff_timer = 0.0

    def is_in_domain(self, pos):
        return self.domain_active and pygame.Vector2(pos).distance_to(self.domain_center) <= self.domain_radius

    def activate_domain(self, game):
        if self.dead or self.domain_active:
            return
        self.domain_active = True
        self.domain_center = pygame.Vector2(self.pos)
        self.domain_timer = 6.5
        self.domain_tick = 0.15
        self.domain_cd = 11.0
        AUDIO.play("domain", 0.85, 300)
        game.boss_domain_message = f"{self.name}: {self.domain_name}"
        game.boss_domain_message_timer = 2.0
        game.shake = max(game.shake, S(10))
        if game.domain_active and game.domains_overlap(self):
            game.start_domain_clash(self)

    def die(self, game):
        if self.dead:
            return
        was_father = self.variant == "father" and game.mode == "arena"
        was_sentinel = self.variant == "sentinel" and game.mode == "arena"
        killer_character = game.player.character
        super().die(game)
        if (not was_father and not was_sentinel) or is_beta_character(killer_character):
            return

        changed = False
        if not SAVE.get("kayk_unlocked", False):
            SAVE["kayk_unlocked"] = True
            changed = True
            AUDIO.play("unlock", 1.0)
            game.unlock_notice = "KAYK DESBLOQUEADO!"
            game.unlock_notice_timer = 5.0

        victories = set(SAVE.get("father_victories", []))
        if killer_character in FATHER_UNLOCK_CHARACTERS and killer_character not in victories:
            victories.add(killer_character)
            SAVE["father_victories"] = sorted(victories)
            changed = True
            game.unlock_notice = f"COLOSSO DO CAOS: {len(victories)}/{len(FATHER_UNLOCK_CHARACTERS)} PERSONAGENS"
            game.unlock_notice_timer = 5.0

        if all(name in victories for name in FATHER_UNLOCK_CHARACTERS) and not SAVE.get("father_unlocked", False):
            SAVE["father_unlocked"] = True
            changed = True
            AUDIO.play("unlock", 1.0)
            game.unlock_notice = "COLOSSO DO CAOS DESBLOQUEADO!"
            game.unlock_notice_timer = 6.0
            game.unlock_achievement("father_unlock")

        if was_sentinel:
            s_victories = set(SAVE.get("sentinel_victories", []))
            if killer_character in FATHER_UNLOCK_CHARACTERS and killer_character not in s_victories:
                s_victories.add(killer_character)
                SAVE["sentinel_victories"] = sorted(s_victories)
                changed = True
                game.unlock_notice = f"HANK: {len(s_victories)}/{len(FATHER_UNLOCK_CHARACTERS)} PERSONAGENS"
                game.unlock_notice_timer = 5.0
            if all(name in s_victories for name in FATHER_UNLOCK_CHARACTERS) and not SAVE.get("hank_unlocked", False):
                SAVE["hank_unlocked"] = True
                changed = True
                AUDIO.play("unlock", 1.0)
                game.unlock_notice = "HANK J. WIMBLETON DESBLOQUEADO!"
                game.unlock_notice_timer = 6.0

        if changed:
            save_data(SAVE)

    def update(self, dt, game):
        if self.dead:
            return
        if self.lira_stat_level("intelligence",game)>=0.999:
            self.flash=max(0,self.flash-dt); self.burst_cd-=dt; self.touch_cd-=dt
            flee=self.pos-game.player.pos
            if flee.length_squared()<=0: flee=vec_from_angle(random.random()*math.tau)
            move_mult=max(0.20,1.0-self.lira_stat_level("speed",game))
            self.pos += flee.normalize()*self.speed*0.72*move_mult*dt
            if self.burst_cd<=0:
                power=self.lira_outgoing_mult(game)
                for _ in range(3):
                    d=vec_from_angle(random.random()*math.tau)
                    game.projectiles.append(Projectile(self.pos,d*S(300),(7+self.wave*0.35)*self.boss_damage_scale*power*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(9),self.color,2.4))
                self.burst_cd=0.75
            self.pos.x=clamp(self.pos.x,self.radius,W-self.radius); self.pos.y=clamp(self.pos.y,S(175)+self.radius,H-S(345)-self.radius)
            return
        self.flash = max(0, self.flash - dt)
        self.forge_slow_timer = max(0.0, getattr(self, "forge_slow_timer", 0.0)-dt)
        boss_move_speed = self.speed * (0.55 if self.forge_slow_timer > 0 else 1.0) * max(0.20,1.0-self.lira_stat_level("speed",game))
        self.burst_cd -= dt
        self.charge_cd -= dt
        self.touch_cd -= dt
        self.clash_buff_timer = max(0.0, self.clash_buff_timer-dt)

        if self.domain_active:
            self.domain_timer -= dt
            self.domain_tick -= dt
            if self.domain_timer <= 0:
                self.domain_active = False
                self.domain_timer = 0.0
            else:
                inside = self.is_in_domain(game.player.pos)
                if self.variant == "father" and inside and self.domain_tick <= 0:
                    # Glonk/Glonk 100% sao imunes a dano inevitavel de Expansao.
                    if game.player.character not in ("Glonk", "Glonk 100% Power"):
                        game.player.take_damage((6 + self.wave*0.22) * self.boss_damage_scale * self.lira_outgoing_mult(game) * difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], game)
                        game.damage_texts.append(DamageText("CAOS!", pygame.Vector2(game.player.pos), RED))
                    self.domain_tick = 0.95
                elif self.variant == "devourer" and inside:
                    drain = (16 + self.wave*0.12) * dt
                    if game.player.stamina > 0:
                        game.player.stamina = max(0, game.player.stamina-drain)
                    elif self.domain_tick <= 0:
                        if game.player.character not in ("Glonk", "Glonk 100% Power"):
                            game.player.take_damage((5 + self.wave*0.15) * self.boss_damage_scale * self.lira_outgoing_mult(game) * difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], game)
                        self.domain_tick = 0.8
                elif self.variant == "sentinel" and inside and self.domain_tick <= 0:
                    for i in range(4):
                        d = vec_from_angle(i*math.pi/2)
                        game.projectiles.append(Projectile(self.domain_center, d*S(355), (6+self.wave*0.35) * self.boss_damage_scale * self.lira_outgoing_mult(game) * difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], "enemy", S(9), CYAN, 2.5))
                    self.domain_tick = 0.72
                elif self.variant == "void" and inside and self.domain_tick <= 0:
                    game.domain_charge = max(0, game.domain_charge-4)
                    game.damage_texts.append(DamageText("SILENCIO", pygame.Vector2(game.player.pos), GRAY))
                    self.domain_tick = 0.9
        else:
            self.domain_cd -= dt
            if self.domain_cd <= 0:
                self.activate_domain(game)

        target_entity = game.get_enemy_target(self.pos)
        to_player = target_entity.pos - self.pos
        dist = max(1, to_player.length())
        d = to_player / dist
        phase2 = self.hp <= self.max_hp * 0.5
        buff = 1.35 if self.clash_buff_timer > 0 else 1.0

        if self.charging > 0:
            self.charging -= dt
            self.pos += self.charge_dir * boss_move_speed * (4.3 if phase2 else 3.4) * buff * dt
        else:
            self.pos += d * boss_move_speed * (1.25 if phase2 else 0.85) * buff * dt
            if self.charge_cd <= 0:
                self.charging = 0.55
                self.charge_dir = pygame.Vector2(d)
                ai_mult = difficulty_cfg(getattr(game,"difficulty","easy"))["ai"] if game.mode=="arena" else 1.0
                self.charge_cd = (2.4 if phase2 else 3.7) / ai_mult

        if self.burst_cd <= 0:
            shots = 14 if phase2 else 9
            for i in range(shots):
                a = i * math.tau / shots + game.time * 0.35
                game.projectiles.append(Projectile(self.pos, vec_from_angle(a) * S(285 if phase2 else 235), (8 + self.wave * 0.5)*buff*self.boss_damage_scale*self.lira_outgoing_mult(game)*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], "enemy", S(11), PINK))
            ai_mult = difficulty_cfg(getattr(game,"difficulty","easy"))["ai"] if game.mode=="arena" else 1.0
            self.burst_cd = (1.15 if phase2 else 1.9) / ai_mult
            game.shake = max(game.shake, S(5))

        if dist < self.radius + target_entity.radius and self.touch_cd <= 0:
            if self.variant == "gula" and target_entity is game.player:
                game.gula_devour(self)
            else:
                target_entity.take_damage((14 + self.wave * 0.8)*buff*self.boss_damage_scale*self.lira_outgoing_mult(game)*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], game)
                if target_entity is game.player and d.length_squared()>0:
                    game.player.pos += d*S(34)*difficulty_cfg(getattr(game,"difficulty","easy"))["force"]
            self.touch_cd = 0.65

        self.pos.x = clamp(self.pos.x, self.radius, W - self.radius)
        self.pos.y = clamp(self.pos.y, S(180) + self.radius, H - S(335) - self.radius)

    def draw(self, offset):
        super().draw(offset)
        p = self.pos + offset
        draw_text(self.name, FONT_S, WHITE, (p.x, p.y + self.radius + S(24)), True)


class SinBoss(Boss):
    """Pecados e Arcebispos: compartilham a base de Boss, mas cada pecado possui uma assinatura propria."""
    def __init__(self, pos, wave, sin_cfg, archbishop=False):
        super().__init__(pos, wave)
        self.sin_key = sin_cfg["key"]
        self.sin_name = sin_cfg["name"]
        self.fragment_key = sin_cfg["fragment"]
        self.archbishop = archbishop
        self.variant = "gula" if self.sin_key == "gula" and not archbishop else "sin_" + self.sin_key
        self.name = ("ARCEBISPO DA " if archbishop else "PECADO: ") + self.sin_name
        self.color = sin_cfg["color"]
        self.radius = S(70 if archbishop else 92)
        # Arcebispo = demonstracao; Pecado verdadeiro = encontro brutal.
        mult = 1.30 if archbishop else 2.35
        self.max_hp *= mult
        self.hp = self.max_hp
        self.speed *= 0.92 if archbishop else 1.08
        self.boss_damage_scale *= 0.82 if archbishop else 1.35
        self.coin_value = 350 if archbishop else 1500
        # V14: Pecados/Arcebispos tambem podem abrir Dominio e causar Clash.
        sin_domains = {
            "wrath": "TRONO DA IRA",
            "pride": "CEU DO ORGULHO",
            "envy": "ESPELHO DA INVEJA",
            "greed": "TESOURO SEM FIM",
            "gula": "BANQUETE SEM FIM",
            "sloth": "SONO DO FIM",
            "lust": "ILUSAO ESCARLATE",
        }
        self.domain_name = sin_domains.get(self.sin_key, "DOMINIO DO PECADO")
        self.domain_desc = "Enquanto ativo, as mecanicas exclusivas deste Pecado aceleram e o Clash e permitido."
        self.domain_active = False
        self.domain_cd = random.uniform(7.0, 9.5) if archbishop else random.uniform(5.2, 7.4)
        self.domain_radius = S(500 if archbishop else 560)
        self.sin_tick = 0.8
        self.sin_aux = 2.0
        self.pride_guard = 0.0
        self.teleport_cd = 2.8
        if self.sin_key == "gula" and not archbishop:
            hunger=max(0,int(SAVE.get("gula_hunger",0)))
            self.max_hp *= 1.25*(1.0+0.35*hunger); self.hp=self.max_hp
            self.speed *= 1.0+min(0.45,0.06*hunger)
            self.boss_damage_scale *= 1.0+min(1.5,0.12*hunger)

    def damage(self, amount, game, source_pos=None, minimal_fx=False):
        raw_resistance = self.lira_stat_level("resistance",game)>=0.999
        if self.sin_key == "pride" and self.pride_guard > 0 and not raw_resistance:
            amount *= 0.28 if not self.archbishop else 0.45
        super().damage(amount, game, source_pos, minimal_fx)

    def update(self, dt, game):
        if self.dead: return
        self.sin_tick -= dt; self.sin_aux -= dt
        # Dentro do proprio Dominio o Pecado "forca" suas mecanicas a acontecerem mais cedo.
        if self.domain_active:
            self.sin_tick -= dt * 0.70
            self.sin_aux -= dt * 0.70
        self.pride_guard=max(0.0,self.pride_guard-dt)
        # Pecado da Preguica: aura azul desacelera o jogador.
        if self.sin_key == "sloth" and self.pos.distance_to(game.player.pos) <= S(560):
            game.sin_sloth_slow = True
        super().update(dt, game)
        if self.dead: return
        if self.lira_stat_level("intelligence",game)>=0.999: return
        strength = 0.60 if self.archbishop else 1.0
        diff_ai = difficulty_cfg(getattr(game,"difficulty","easy"))["ai"] if game.mode=="arena" else 1.0
        if self.sin_key == "wrath" and self.sin_tick <= 0:
            shots = 8 if self.archbishop else (12 if self.hp > self.max_hp*0.5 else 18)
            for i in range(shots):
                d=vec_from_angle(i*math.tau/shots + game.time*0.2)
                game.projectiles.append(Projectile(self.pos,d*S(330), (8+effective_combat_wave(game.wave)*0.22)*self.boss_damage_scale*self.lira_outgoing_mult(game)*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(9),RED,2.5))
            self.sin_tick = (1.8 if self.archbishop else 1.15) / diff_ai
        elif self.sin_key == "pride" and self.sin_aux <= 0:
            self.pride_guard = 0.85 if self.archbishop else 1.45
            game.damage_texts.append(DamageText("EU ESTOU ACIMA",pygame.Vector2(self.pos),YELLOW,0.8))
            self.sin_aux = (4.6 if self.archbishop else 3.6) / diff_ai
        elif self.sin_key == "envy" and self.sin_tick <= 0:
            to=game.player.pos-self.pos
            if to.length_squared()>0:
                a=math.atan2(to.y,to.x)
                for off in (-0.24,0,0.24):
                    game.projectiles.append(Projectile(self.pos,vec_from_angle(a+off)*S(390),(9+effective_combat_wave(game.wave)*0.20)*self.boss_damage_scale*self.lira_outgoing_mult(game)*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(10),GREEN,3.0))
            self.speed=max(self.speed, game.player.base_speed*(0.72 if self.archbishop else 0.95))
            self.sin_tick=(1.55 if self.archbishop else 1.05) / diff_ai
        elif self.sin_key == "greed" and self.sin_aux <= 0:
            if self.pos.distance_to(game.player.pos) <= S(520):
                stolen=min(game.run_coins, max(5,int(game.run_coins*(0.03 if self.archbishop else 0.08))))
                game.run_coins=max(0,game.run_coins-stolen)
                self.hp=min(self.max_hp,self.hp+stolen*(2.0 if self.archbishop else 4.0))
                game.damage_texts.append(DamageText(f"ROUBOU {stolen}",pygame.Vector2(game.player.pos),ORANGE,0.8))
            self.sin_aux=(3.2 if self.archbishop else 2.1) / diff_ai
        elif self.sin_key == "gula":
            # Contato do Pecado verdadeiro e o devorar classico; o Arcebispo apenas causa dano normal.
            pass
        elif self.sin_key == "sloth" and self.sin_tick <= 0:
            # Campo pesado: projeteis azuis lentos fecham espaco ao redor do jogador.
            for i in range(6 if self.archbishop else 10):
                d=vec_from_angle(i*math.tau/(6 if self.archbishop else 10))
                game.projectiles.append(Projectile(self.pos,d*S(205),(7+effective_combat_wave(game.wave)*0.16)*self.boss_damage_scale*self.lira_outgoing_mult(game)*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(13),BLUE,4.0))
            self.sin_tick=(2.4 if self.archbishop else 1.7) / diff_ai
        elif self.sin_key == "lust" and self.sin_aux <= 0:
            # Sem conteudo sexual: mecanica e uma ilusao violeta que teleporta o boss e cria um leque de projeteis.
            to=game.player.pos-self.pos
            if to.length_squared()>0:
                d=to.normalize(); self.pos=game.player.pos-d*S(330)
                a=math.atan2(d.y,d.x)
                for off in (-0.42,-0.21,0,0.21,0.42):
                    game.projectiles.append(Projectile(self.pos,vec_from_angle(a+off)*S(360),(8+effective_combat_wave(game.wave)*0.18)*self.boss_damage_scale*self.lira_outgoing_mult(game)*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(9),PINK,3.0))
            self.sin_aux=(3.4 if self.archbishop else 2.25) / diff_ai

    def die(self, game):
        if self.dead: return
        Enemy.die(self, game)
        if self.archbishop or game.mode != "arena" or is_beta_character(game.player.character):
            return
        # O fragmento vai direto ao inventario em runs normais.
        # BOSS RUSH e excecao: nunca entrega Pedacos dos Pecados.
        fragment_granted = getattr(game,"game_mode","normal") != "boss_rush"
        if fragment_granted:
            game.collect_forge_material(self.fragment_key,1)
        defeated=set(SAVE.get("sin_defeats",[])); defeated.add(self.sin_key); SAVE["sin_defeats"]=sorted(defeated)
        achievement_key = "gula_defeated" if self.sin_key == "gula" else f"sin_{self.sin_key}_defeated"
        game.unlock_achievement(achievement_key)
        if len(defeated) >= 7:
            game.unlock_achievement("all_sins")
        if all(game.forge_material_amount(k)>=1 for k in SIN_FRAGMENTS):
            game.unlock_achievement("all_sin_fragments")
        if self.sin_key == "gula":
            SAVE["gula_defeats"]=SAVE.get("gula_defeats",0)+1
        save_data(SAVE)
        if fragment_granted:
            game.unlock_notice=f"PEDACO DO PECADO: {self.sin_name}"
            game.unlock_notice_timer=4.5
        elif getattr(game,"game_mode","normal") == "boss_rush":
            game.unlock_notice="BOSS RUSH: SEM PEDACO DO PECADO"
            game.unlock_notice_timer=2.6

    def draw(self, offset):
        super().draw(offset)
        p=self.pos+offset
        if self.sin_key=="pride" and self.pride_guard>0:
            pygame.draw.circle(SCREEN,YELLOW,(int(p.x),int(p.y)),self.radius+S(16),max(2,S(4)))
        draw_text("ARCEBISPO" if self.archbishop else "PECADO",FONT_S,self.color,(p.x,p.y+self.radius+S(50)),True)

class GulaBoss(Boss):
    """Versao especial da Gula. Lembra quantas vezes ja devorou o jogador."""
    def __init__(self, pos, wave=500):
        super().__init__(pos, wave)
        hunger = max(0, int(SAVE.get("gula_hunger", 0)))
        self.variant = "gula"
        self.name = "A GULA"
        self.domain_name = "BANQUETE SEM FIM"
        self.domain_desc = "Tudo que entra vira alimento para uma fome que lembra de voce."
        self.color = (120, 18, 38)
        self.radius = S(92)
        self.hunger_level = hunger
        self.max_hp *= 1.75 * (1.0 + 0.55 * hunger)
        self.hp = self.max_hp
        self.speed *= 1.10 * (1.0 + min(0.65, 0.08 * hunger))
        self.boss_damage_scale *= 1.25 + min(2.0, 0.18 * hunger)
        self.coin_value = 5000 + 750 * hunger
        self.burst_cd = max(0.38, 1.15 - 0.07 * hunger)
        self.charge_cd = max(0.65, 2.0 - 0.10 * hunger)
        self.domain_cd = 2.8
        self.domain_radius = S(560)

    def die(self, game):
        if self.dead:
            return
        # Usa Enemy.die diretamente para nao acionar desbloqueios do Colosso do Caos.
        Enemy.die(self, game)
        if not is_beta_character(game.player.character):
            SAVE["gula_defeats"] = SAVE.get("gula_defeats", 0) + 1
            save_data(SAVE)
            game.unlock_achievement("gula_defeated")
        game.unlock_notice = "A GULA FOI DERROTADA. POR ENQUANTO."
        game.unlock_notice_timer = 6.0

    def update(self, dt, game):
        before = len(game.projectiles)
        # O comportamento-base continua valendo: movimento, investida, dominio e rajadas.
        super().update(dt, game)
        if self.dead:
            return
        if self.lira_stat_level("intelligence",game)>=0.999:
            return
        # Todo projetil criado por A Gula recebe a marca de devorar.
        for pr in game.projectiles[before:]:
            if pr.owner == "enemy":
                pr.gula_devour = True
                pr.color = (190, 35, 60)
                pr.radius = max(pr.radius, S(13))
        # Quanto mais experiencias ela devora, mais projeteis extras produz.
        if self.hunger_level > 0 and random.random() < min(0.18, dt * (0.8 + self.hunger_level*0.15)):
            target = game.player.pos - self.pos
            if target.length_squared() > 0:
                pr = Projectile(self.pos, target.normalize()*S(360 + min(240, self.hunger_level*18)), 1, "enemy", S(15), (220,45,70), 3.2)
                pr.gula_devour = True
                game.projectiles.append(pr)

    def draw(self, offset):
        super().draw(offset)
        p = self.pos + offset
        draw_text(f"FOME {self.hunger_level}", FONT_S, RED, (p.x, p.y + self.radius + S(54)), True)



class DivineDog:
    """Cao Divino do Potential Man. Possui HP proprio, regenera e ataca sozinho."""
    def __init__(self, pos, player, side=1):
        self.pos = pygame.Vector2(pos)
        self.player_ref = player
        self.side = side
        self.radius = S(24)
        self.max_hp = 105.0
        self.hp = self.max_hp
        self.damage = max(8.0, player.base_damage * 0.62) * player.passive_ally_damage_mult() * getattr(player,"summon_power_mult",1.0)
        self.speed = S(205) * getattr(player,"summon_power_mult",1.0)
        if getattr(player,"potential_coordinated_pack",False): self.damage*=1.20; self.speed*=1.20
        if getattr(player,"potential_ten_shadows_general",False): self.damage*=1.40; self.speed*=1.15
        self.attack_cd = 0.0
        self.dead = False
        self.guardian = False
        self.color = (235,235,242) if side > 0 else (72,76,88)

    def take_damage(self, amount, game):
        if self.dead: return
        amount*=max(0.0,1.0-getattr(self.player_ref,"passive_ally_damage_reduction",lambda:0.0)())
        self.hp -= max(0.0, amount)
        game.spawn_particles(self.pos, self.color, 4)
        if self.hp <= 0:
            self.dead = True
            self.hp = 0
            others = [x for x in game.potential_summons if isinstance(x, DivineDog) and x is not self and not x.dead]
            if not others and game.player.character == "Potential Man":
                game.player.potential_dog_cd = max(game.player.potential_dog_cd, 3.5 if game.player.potential_ten_shadows_general else 7.0)
                game.damage_texts.append(DamageText("CAES DERROTADOS - 7s", pygame.Vector2(game.player.pos), RED, 1.0))

    def update(self, dt, game):
        if self.dead: return False
        self.attack_cd = max(0.0, self.attack_cd-dt)
        self.hp = min(self.max_hp, self.hp + self.max_hp*0.035*dt)
        targets=[e for e in game.enemies if not e.dead]
        maho = getattr(game, "mahoraga", None)
        if getattr(game, "mahoraga_hostile_to_dogs", False) and maho is not None and not maho.dead:
            targets.append(maho)
        if not targets:
            desired = game.player.pos + pygame.Vector2(self.side*S(55), S(35))
            d = desired-self.pos
            if d.length_squared()>S(10)**2:
                self.pos += d.normalize()*self.speed*0.70*dt
            return True
        target=min(targets,key=lambda e:e.pos.distance_to(self.pos))
        d=target.pos-self.pos; dist=max(1.0,d.length())
        if dist > self.radius+target.radius+S(10):
            self.pos += d/dist*self.speed*dt
        elif self.attack_cd<=0:
            old=game.current_damage_kind; game.current_damage_kind="divine_dog"
            if isinstance(target, MahoragaSummon):
                target.take_damage(self.damage, game, self.pos, from_player=False)
            else:
                target.damage(self.damage,game,self.pos)
            game.current_damage_kind=old
            self.attack_cd=0.55
        self.pos.x=clamp(self.pos.x,self.radius,W-self.radius)
        self.pos.y=clamp(self.pos.y,S(175)+self.radius,H-S(340)-self.radius)
        return not self.dead

    def draw(self, offset):
        p=self.pos+offset
        pygame.draw.circle(SCREEN,self.color,(int(p.x),int(p.y)),self.radius)
        pygame.draw.polygon(SCREEN,self.color,[(p.x-self.radius*0.7,p.y-self.radius*0.7),(p.x-self.radius*0.25,p.y-self.radius*1.35),(p.x,p.y-self.radius*0.65)])
        pygame.draw.polygon(SCREEN,self.color,[(p.x+self.radius*0.7,p.y-self.radius*0.7),(p.x+self.radius*0.25,p.y-self.radius*1.35),(p.x,p.y-self.radius*0.65)])
        pygame.draw.circle(SCREEN,DARK,(int(p.x-self.radius*0.30),int(p.y-self.radius*0.08)),max(2,S(3)))
        pygame.draw.circle(SCREEN,DARK,(int(p.x+self.radius*0.30),int(p.y-self.radius*0.08)),max(2,S(3)))
        bw=self.radius*2
        pygame.draw.rect(SCREEN,DARK,(p.x-bw/2,p.y-self.radius-S(14),bw,S(6)))
        pygame.draw.rect(SCREEN,GREEN,(p.x-bw/2,p.y-self.radius-S(14),bw*clamp(self.hp/self.max_hp,0,1),S(6)))


class MahoragaSummon:
    """Mahoraga e uma entidade neutra: corta inimigos e o proprio jogador."""
    def __init__(self, pos, player, wave):
        self.pos=pygame.Vector2(pos)
        self.player_ref=player
        self.radius=S(72)
        self.max_hp=1100.0 + max(0,wave-1)*38.0
        self.hp=self.max_hp
        self.speed=S(170)
        self.damage=max(26.0,player.base_damage*1.35)
        self.attack_cd=0.45
        self.dead=False
        self.guardian=True
        self.resistance=0.0
        self.player_damage_adaptation=0.0
        self.wave_adaptations=0
        self.color=(220,220,205)
        self.slash_fx=0.0
        self.facing=pygame.Vector2(1,0)

    def take_damage(self, amount, game, source_pos=None, from_player=False):
        if self.dead:return
        dealt=max(0.0,amount)*(1.0-self.resistance)
        self.hp -= dealt
        if from_player and dealt > 0.0:
            domain_raw = getattr(game, "current_domain_charge_raw_override", None)
            game.current_domain_charge_raw_override = None
            if domain_raw is not None and domain_raw > 0.0:
                game.add_domain_charge(domain_raw)
        if from_player:
            if not getattr(game, "mahoraga_hostile_to_dogs", False):
                game.damage_texts.append(DamageText("MAHORAGA PROVOCADO", pygame.Vector2(self.pos), PINK, 0.65))
            game.mahoraga_hostile_to_dogs = True
        game.spawn_particles(self.pos,self.color,4)
        if self.hp<=0:
            self.hp=0; self.dead=True
            game.damage_texts.append(DamageText("MAHORAGA CAIU",pygame.Vector2(self.pos),GRAY,1.0))

    def adapt(self, game, amount=0.10, heal=False, announce=True):
        if self.dead:
            return
        self.wave_adaptations += 1
        self.resistance = min(0.80, self.resistance + amount)
        # O dano adaptativo cresce SOMENTE quando Mahoraga atinge o jogador.
        # O dano que ele causa aos inimigos permanece inalterado.
        self.player_damage_adaptation = min(0.80, self.player_damage_adaptation + amount)
        if heal:
            self.hp = self.max_hp
        if announce:
            game.damage_texts.append(DamageText(f"ADAPTACAO {int(self.resistance*100)}%",pygame.Vector2(self.pos),YELLOW,1.0))

    def end_wave_adapt(self, game):
        if self.dead:return
        self.adapt(game, 0.10, heal=True, announce=True)

    def update(self, dt, game):
        if self.dead:return False
        self.attack_cd=max(0.0,self.attack_cd-dt)
        self.slash_fx=max(0.0,self.slash_fx-dt)
        candidates=[e for e in game.enemies if not e.dead]
        # O jogador e deliberadamente um alvo valido.
        target=game.player
        best=self.pos.distance_to(game.player.pos)
        for e in candidates:
            d=self.pos.distance_to(e.pos)
            if d<best: target=e; best=d
        d=target.pos-self.pos
        if d.length_squared()>0:
            self.facing=d.normalize()
        if best>S(150):
            self.pos += self.facing*self.speed*dt
        if self.attack_cd<=0:
            rng=S(180)
            hit=False
            old=game.current_damage_kind; game.current_damage_kind="mahoraga_slash"
            for e in list(game.enemies):
                if not e.dead and e.pos.distance_to(self.pos)<=rng+e.radius:
                    e.damage(self.damage,game,self.pos); hit=True
            # Tambem corta o invocador se ele estiver perto.
            if game.player.pos.distance_to(self.pos)<=rng+game.player.radius:
                base_player_damage=max(12.0,min(60.0,12.0+game.wave*0.08))
                game.player.take_damage(base_player_damage*(1.0+self.player_damage_adaptation),game); hit=True
            game.current_damage_kind=old
            if hit:
                self.slash_fx=0.14
                AUDIO.play("kevyn_sword",0.68,90)
            self.attack_cd=0.72
        self.pos.x=clamp(self.pos.x,self.radius,W-self.radius)
        self.pos.y=clamp(self.pos.y,S(175)+self.radius,H-S(340)-self.radius)
        return not self.dead

    def draw(self, offset):
        p=self.pos+offset
        pygame.draw.circle(SCREEN,self.color,(int(p.x),int(p.y)),self.radius)
        pygame.draw.circle(SCREEN,DARK,(int(p.x),int(p.y)),self.radius,max(2,S(5)))
        # Roda de adaptacao simples, sem sprites pesados.
        wr=self.radius+S(28)
        pygame.draw.circle(SCREEN,YELLOW,(int(p.x),int(p.y-wr)),S(10),max(2,S(3)))
        for i in range(8):
            d=vec_from_angle(i*math.tau/8)
            a=p+d*(self.radius+S(14)); b=p+d*(self.radius+S(36))
            pygame.draw.line(SCREEN,YELLOW,a,b,max(2,S(4)))
        draw_text(f"MAHORAGA {int(self.resistance*100)}%",FONT_S,WHITE,(p.x,p.y-self.radius-S(58)),True)
        bw=self.radius*2.2
        pygame.draw.rect(SCREEN,DARK,(p.x-bw/2,p.y+self.radius+S(10),bw,S(8)))
        pygame.draw.rect(SCREEN,GREEN,(p.x-bw/2,p.y+self.radius+S(10),bw*clamp(self.hp/self.max_hp,0,1),S(8)))
        if self.slash_fx>0:
            a=math.atan2(self.facing.y,self.facing.x); r=S(155)
            rect=pygame.Rect(p.x-r,p.y-r,r*2,r*2)
            pygame.draw.arc(SCREEN,WHITE,rect,-(a+0.8),-(a-0.8),S(10))


class Player:
    def __init__(self, game, character="Ycaro"):
        self.character = character if character in CHARACTER_CONFIG else "Ycaro"
        cfg = CHARACTER_CONFIG[self.character]
        self.radius = S(28)
        self.pos = pygame.Vector2(W / 2, H * 0.62)
        self.facing = pygame.Vector2(0, -1)
        self.color = cfg["color"]
        self.passive_keys = passive_equipped_keys(self.character) if not is_beta_character(self.character) else []
        self.passive_static = passive_static_effects(self.passive_keys)
        self.passive_upgrade_count = 0
        self.passive_wave_count = 0
        self.passive_dash_buff_timer = 0.0
        self.passive_protagonist_used = False
        self.passive_progress_hp_base = 0.0
        # Beta usa valores-base fixos: nao recebe nem aplica pontos de evolucao.
        evo = evolution_profile(self.character) if not is_beta_character(self.character) else {key: 0 for key in EVOLUTION_STAT_KEYS}
        self.evolution = evo
        self.evo_resistance = evo.get("resistance", 0)
        self.evo_parry = evo.get("parry", 0)
        self.base_speed = S(cfg["speed"]) * (1 + 0.03 * SAVE["speed_level"]) * (1 + 0.015 * evo.get("speed", 0))
        self.base_speed *= max(0.10, 1.0 + self.passive_static.get("move",0.0))
        self.speed_mult = 1.0
        self.speed_buff = 0
        self.still_timer = 0.0

        self.max_hp = cfg["hp"] + SAVE["vitality_level"] * 8 + evo.get("hp", 0) * 6
        if self.character not in ("Sans", "Glonk 100% Power"):
            self.max_hp *= max(0.10, 1.0 + self.passive_static.get("hp",0.0))
        self.hp = self.max_hp
        self.max_stamina = cfg["stamina"] + SAVE["vitality_level"] * 6 + SAVE.get("stamina_level", 0) * 10 + evo.get("stamina", 0) * 5
        if self.character == "Sans":
            # Sans sempre possui exatamente 1 HP. Investimentos em HP viram reserva extra de esquiva.
            self.max_hp = 1
            self.hp = 1
            self.max_stamina += evo.get("hp", 0) * 3
        elif self.character == "Glonk 100% Power":
            # A piada do personagem e ter exatamente 1 HP; evolucao de HP vira Estamina.
            self.max_hp = 1
            self.hp = 1
            self.max_stamina += evo.get("hp", 0) * 2
        self.stamina = self.max_stamina
        self.stamina_regen = cfg["regen"] * (1 + 0.06 * SAVE.get("regen_level", 0)) * (1 + 0.015 * evo.get("stamina", 0))
        self.stamina_regen_delay = 0.0

        self.base_damage = cfg["damage"] * (1 + 0.08 * SAVE["damage_level"]) * (1 + 0.03 * evo.get("strength", 0))
        self.damage_mult = 1.0
        self.attack_cd = 0
        self.dash_cd = 0
        self.parry_cd = 0
        self.parry_time = 0
        self.dash_time = 0
        self.dash_dir = pygame.Vector2()
        self.invuln = 0
        self.shield = 0

        self.weapon = cfg["weapon"]
        self.weapon_name = cfg.get("weapon_name", "NADA")
        self.weapons = ["ESPADA", "PISTOLA", "SHOTGUN", "CAJADO", "PISTOLAS DUPLAS", "NADA", "ABACAXI BUMERANGUE", "INVESTIDA", "GOLPE EM AREA", "OSSOS / BLASTER"]
        self.domain_name = cfg["domain"]

        # Flags/valores de build. As cartas ligam estes efeitos durante a run.
        self.projectile_pierce = 0
        self.projectile_bonus = 1.0
        self.stamina_on_hit = 1.0
        self.execute_bonus = 0
        self.crit_chance = min(0.20, 0.02 * SAVE.get("crit_level", 0)) + self.passive_static.get("crit",0.0)
        self.crit_damage_mult = self.passive_static.get("crit_mult",1.5)
        self.drop_bonus = 0.02 * SAVE.get("orb_level", 0)
        self.passive_coin_bonus = self.passive_static.get("coins",0.0)
        self.passive_collect_bonus = self.passive_static.get("collect",0.0)
        self.passive_damage_reduction = self.passive_static.get("damage_reduction",0.0)
        self.passive_domain_recharge = self.passive_static.get("domain_recharge",0.0)
        self.passive_domain_damage = self.passive_static.get("domain_damage",0.0)
        self.passive_domain_duration = self.passive_static.get("domain_duration",0.0)
        self.passive_attack_speed = self.passive_static.get("attack_speed",0.0)
        self.passive_attack_recharge = self.passive_static.get("attack_recharge",0.0)
        self.passive_dash_recharge = self.passive_static.get("dash_recharge",0.0)
        self.passive_ally_damage = self.passive_static.get("ally_damage",0.0)
        self.passive_wave_heal = self.passive_static.get("wave_heal",0.0)
        self.passive_crit_kill_coins = self.passive_static.get("crit_kill_coins",0.0)
        self.passive_fatal_save = bool(self.passive_static.get("fatal_save",False))
        self.radius = max(S(18), int(self.radius * self.passive_static.get("hitbox_scale",1.0)))
        self.kill_stamina = 0.0
        self.questionable_hemo = False
        self.overclock = False
        self.last_breath = False
        self.explosive_parry = False
        self.predator = False
        self.predator_timer = 0.0
        self.ghost_dash = False
        self.blood_debt = False
        self.vampire_heart = False
        self.orb_rain = False
        self.ricochet_chance = 0.0
        self.chain_execution = False
        self.beyond_limit = False
        self.second_bar = False
        self.broken_time = False
        self.giant_hunter = False
        self.orb_magnet = False
        self.eternal_combo = False
        self.domain_evolution = False
        self.glass_cannon = False
        self.insatiable_hunger = False
        self.devil_pact = False
        self.no_brakes = False
        self.one_last_game = False
        self.god_not_watching = False
        self.revive_used = False
        # Power Ups 2.0 - universais/hibridos
        self.hybrid_blade_vampire = False
        self.hybrid_melee_hits = 0
        self.hybrid_chaotic_ammo = False
        self.hybrid_supreme_command = False
        self.hybrid_inertia = False
        self.hybrid_inertia_timer = 0.0
        self.hybrid_overpressure = False
        self.hybrid_resonant_domain = False
        self.hybrid_auto_loader = False
        self.hybrid_kinetic_rebound = False
        self.combo_engine = False
        self.summon_power_mult = 1.0

        # Ana
        self.ana_blind_spot = False
        self.ana_double_shot = False
        self.ana_reality_error = 0.0
        self.ana_vector_step = False
        self.ana_causal_eye = False
        self.ana_reality_exe = False
        self.ana_pocket_army = False
        self.ana_continuity = False
        self.ana_all_ana = False
        self.ana_unstable_reality = False
        self.ana_spawn_counter = 0
        # Kevyn
        self.kevyn_sword_range = 1.0
        self.kevyn_sword_cost_reduction = 0
        self.kevyn_sword_bonus = 1.0
        self.kevyn_human_wall = False
        self.kevyn_time_counter = False
        self.kevyn_immovable = False
        self.kevyn_hungry_sword = False
        self.kevyn_time_stops = False
        self.kevyn_second_cut = False
        self.kevyn_thirsty_blade = False
        self.kevyn_absolute_parry = False
        self.kevyn_absolute_parry_ready = False
        self.kevyn_one_vs_hundred = False
        # Ycaro
        self.ycaro_point_blank = False
        self.ycaro_extra_pellets = 0
        self.ycaro_pellet_speed = 1.0
        self.ycaro_domino = False
        self.ycaro_aggressive_reload = False
        self.ycaro_sawed_off = False
        self.ycaro_hunter = False
        self.ycaro_no_too_close = False
        self.ycaro_heavy_lead = False
        self.ycaro_twelve_barrels = False
        self.ycaro_wounded_hunter = False
        self.ycaro_wrong_room = False
        # Kayk
        self.kayk_extra_pair = 0
        self.kayk_soul_pierce = 0
        self.kayk_spectral_step = False
        self.kayk_pistol_bonus = 1.0
        self.kayk_armed_procession = False
        self.kayk_thousand_souls = False
        self.kayk_crossfire = False
        self.kayk_soul_mark = False
        self.kayk_two_triggers = False
        self.kayk_ballistic_procession = False
        self.kayk_procession_bonus = False
        # Ana / cajado
        self.ana_blast_mult = 1.0
        self.ana_miniana_speed = 1.0
        # Pedro
        self.pedro_damage_mult = 1.0
        self.pedro_speed_mult = 1.0
        self.pedro_range_mult = 1.0
        self.pedro_return_hit = True
        self.pedro_return_damage_mult = 1.0
        self.pedro_explosive = False
        self.pedro_extra_boomerangs = 0
        self.pedro_steel_peel = False
        self.pedro_crown = False
        self.pedro_x_destiny = False
        self.pedro_saturn = False
        self.pedro_double_crop = False
        self.pedro_predator_fruit = False
        self.pedro_industrial_plantation = False
        # Ruan
        self.ruan_dash_damage_mult = 1.0
        self.ruan_servant_hp_mult = 1.0
        self.ruan_servant_damage_mult = 1.0
        self.ruan_servant_speed_mult = 1.0
        self.ruan_necro_step = False
        self.ruan_growing_army = False
        self.ruan_guardian_mult = 1.0
        self.ruan_king_dead = False
        self.ruan_attack_time = 0.0
        self.ruan_attack_dir = pygame.Vector2()
        self.ruan_hit_ids = set()
        self.ruan_domain_charge_awarded = False
        self.ruan_forced_recruitment = False
        self.ruan_attack_formation = False
        self.ruan_no_one_left = False
        self.ruan_endless_army = False
        self.ruan_direct_kills = 0
        # Colosso do Caos jogavel
        self.father_radius_mult = 1.0
        self.father_damage_mult = 1.0
        self.father_clear_projectiles = False
        self.father_boss_bonus = False
        self.father_boss_weapon_mult = 1.0
        self.father_boss_heal = False
        self.father_domain_radius_mult = 1.0
        self.father_domain_refill = False
        self.father_growing_authority = False
        self.father_next_radius_bonus = 0.0
        self.father_repeat_slap = False
        self.father_i_rule_here = False
        self.father_paternal_sentence = False
        # Sans beta
        self.is_moving = False
        self.sans_exhausted = False
        self.sans_blaster_cd = 0.0
        self.sans_melee_fx = 0.0
        self.sans_melee_dir = pygame.Vector2(1, 0)
        self.sans_dodge_cost = max(8.0, 20.0 * max(0.625, 1.0 - 0.015*self.evo_resistance))
        self.sans_stubborn_bone = False
        self.sans_blue_shortcut = False
        self.sans_karmic_judgement = False
        self.sans_worse_time = False
        # Strikada Egoista
        self.strikada_bounces = 4
        self.strikada_extra_balls = 0
        self.strikada_homing = False
        self.strikada_kill_explosion = False
        self.strikada_self_pass = False
        self.strikada_metavision = False
        self.strikada_protagonist = False
        self.strikada_impossible_goal = False
        self.strikada_next_infinite = False
        # Glonk 100% Power
        self.glonk_power_fx = 0.0
        self.glonk_power_dir = pygame.Vector2(1,0)
        self.glonk_industrial_tongue = False
        self.glonk_learned = False
        self.glonk_101_power = False
        self.glonk_101_ready = False
        # Vinicius 13
        self.vinicius_phrase_cd = 0.0
        self.vinicius_premium_scrap = False
        self.vinicius_auto_maintenance = False
        self.vinicius_production_line = False
        self.vinicius_truly_automatic = False
        # Potential Man jogavel
        self.potential_dog_cd = 0.0
        self.potential_hold_timer = 0.0
        self.potential_hold_triggered = False
        self.potential_frog_fx = 0.0
        self.potential_frog_dir = pygame.Vector2(1, 0)
        self.potential_coordinated_pack = False
        self.potential_amphibian_shadow = False
        self.potential_early_wheel = False
        self.potential_ten_shadows_general = False
        # Vasco - O Apostador Incansavel
        self.vasco_bet_level = 50.0
        self.vasco_jackpot_timer = 0.0
        self.vasco_jackpot_duration = 8.0
        self.vasco_jackpot_used_this_wave = False
        self.vasco_took_damage_this_wave = False
        self.vasco_dharma_reduction = 0.0
        self.vasco_particle_cd = 0.0
        self.vasco_immune_text_cd = 0.0
        self.vasco_marked_chip = False
        self.vasco_high_stakes = False
        self.vasco_sevens = False
        self.vasco_win_streak = 0
        self.vasco_house_loses = False
        # Lira
        self.lira_thick_bar = False
        self.lira_four_words = False
        self.lira_torn_page = False
        self.lira_nothing_published = False
        self.lira_domain_buffs=set()
        self.lira_life_bonus=0.0
        self.hank_charge_time = 0.0
        self.hank_charge_required = 1.5
        self.hank_domain_hold = 0.0
        self.hank_domain_triggered = False
        self.hank_artillery_cd = 0.0
        self.hank_cannon_planted = False
        self.hank_high_caliber = False
        self.hank_bolt_cycle = False
        self.hank_confirmed_target = False
        self.hank_madness_combat = False
        # Sukuna: ULT Fuuga + Santuário Malevolente + Dedos (progressao somente da run).
        self.sukuna_slash_fx = 0.0
        self.sukuna_fingers = 0
        self.sukuna_finger_hp_base = None
        self.sukuna_domain_hold = 0.0
        self.sukuna_domain_triggered = False
        self.sukuna_dismantle = False
        self.sukuna_adaptive_cut = False
        self.sukuna_open_furnace = False
        self.sukuna_king_curses = False
        self.sukuna_fuuga_synergy = False
        # Rip_Indra beta
        self.rip_hold_time = 0.0
        self.rip_hold_threshold = 0.28
        self.rip_charge_max = 2.0
        self.rip_sword_damage_mult = 1.0
        self.rip_range_mult = 1.0
        self.rip_admin_rage = False
        self.rip_triple_authority = False
        self.rip_click_fx = 0.0
        self.rip_click_dir = pygame.Vector2(1, 0)
        # Hisoka beta
        self.hisoka_hold_time = 0.0
        self.hisoka_hold_threshold = 0.28
        self.hisoka_charge_max = 1.8
        self.hisoka_revived = False
        self.hisoka_card_trick = False
        self.hisoka_elastic_gum = False
        self.hisoka_paralyzing_joker = False
        self.hisoka_show_must_go_on = False
        # Glonk normal
        self.glonk_not_supposed = False
        self.glonk_professional_coward = False
        self.glonk_last_one = False

        # Arma fabricada/equipada na Forja. Beta nunca recebe equipamento persistente.
        equipped = SAVE.get("equipped_weapons", {}) if isinstance(SAVE.get("equipped_weapons", {}), dict) else {}
        self.forge_weapon = None if is_beta_character(self.character) else equipped.get(self.character)
        self.forge_kevyn = self.forge_weapon == "kevyn_counterblade"
        self.forge_ana = self.forge_weapon == "ana_reflex_staff"
        self.forge_kayk = self.forge_weapon == "kayk_grave_pistols"
        self.forge_pedro = self.forge_weapon == "pedro_king_pineapple"
        self.forge_ruan = self.forge_weapon == "ruan_hell_pact"
        self.forge_ycaro = self.forge_weapon == "ycaro_golden_hunter"
        self.forge_father = self.forge_weapon == "father_sentence_fist"
        self.divine_kevyn = self.forge_weapon == "kevyn_seven_faces"
        self.divine_ana = self.forge_weapon == "ana_longinus"
        self.divine_kayk = self.forge_weapon == "kayk_big_builder"
        self.divine_ycaro = self.forge_weapon == "ycaro_shotgun_shelly"
        self.divine_ruan = self.forge_weapon == "ruan_monarch_cloak"
        self.divine_pedro = self.forge_weapon == "pedro_hunting_time"
        self.divine_vasco = self.forge_weapon == "vasco_dharma_helm"
        self.divine_attack_hold = 0.0
        self.divine_attack_triggered = False
        self.divine_parry_hold = 0.0
        self.divine_parry_triggered = False
        self.divine_domain_hold = 0.0
        self.divine_domain_triggered = False
        self.divine_dash_hold = 0.0
        self.divine_dash_triggered = False
        self.longinus_next_threshold = 2.0
        if self.divine_pedro:
            # V14: Tempo de Caca manteve apenas +100% velocidade; bonus de alcance foi removido.
            self.pedro_speed_mult *= 2.0
        self.kayk_builder_wave_used = -1
        self.ana_forge_cd = 0.0
        if self.forge_kevyn:
            self.kevyn_sword_range *= 1.45
        if self.forge_pedro:
            self.pedro_speed_mult *= 1.35
        if self.forge_ycaro:
            self.ycaro_extra_pellets += 2
            self.projectile_pierce += 1
        if self.forge_father:
            self.father_radius_mult *= 1.25
            self.father_damage_mult *= 1.20
            self.father_clear_projectiles = True
        # Modificadores genericos das novas armas da Forja.
        recipe = FORGE_WEAPON_BY_KEY.get(self.forge_weapon, {}) if self.forge_weapon else {}
        mods = recipe.get("mods", {}) if isinstance(recipe, dict) else {}
        if mods:
            self.base_damage *= float(mods.get("damage", 1.0))
            self.base_speed *= float(mods.get("speed", 1.0))
            hp_bonus = float(mods.get("hp", 0.0))
            if hp_bonus and self.character not in ("Sans", "Glonk 100% Power"):
                self.max_hp += hp_bonus; self.hp += hp_bonus
            sta_bonus = float(mods.get("stamina", 0.0)); self.max_stamina += sta_bonus; self.stamina += sta_bonus
            self.stamina_regen *= float(mods.get("regen", 1.0))
            self.crit_chance += float(mods.get("crit", 0.0))
            self.projectile_pierce += int(mods.get("pierce", 0))
            self.shield += int(mods.get("shield", 0))
            self.kevyn_sword_range *= float(mods.get("kevyn_range", 1.0))
            self.ana_miniana_speed *= float(mods.get("ana_miniana_speed", 1.0))
            self.ana_blast_mult *= float(mods.get("ana_blast", 1.0))
            self.ana_three_bias = float(mods.get("ana_three_bias", 0.0))
            self.kayk_extra_pair += int(mods.get("kayk_pairs", 0))
            self.pedro_speed_mult *= float(mods.get("pedro_speed", 1.0))
            self.pedro_range_mult *= float(mods.get("pedro_range", 1.0))
            self.pedro_extra_boomerangs += int(mods.get("pedro_extra", 0))
            self.ruan_dash_damage_mult *= float(mods.get("ruan_dash", 1.0))
            self.ruan_servant_hp_mult *= float(mods.get("ruan_friend_hp", 1.0))
            self.ruan_servant_damage_mult *= float(mods.get("ruan_friend_damage", 1.0))
            self.ruan_servant_speed_mult *= float(mods.get("ruan_friend_speed", 1.0))
            self.ycaro_extra_pellets += int(mods.get("ycaro_pellets", 0))
            self.father_radius_mult *= float(mods.get("father_radius", 1.0))
            self.father_boss_weapon_mult *= float(mods.get("father_boss", 1.0))
            self.father_domain_radius_mult *= float(mods.get("father_domain", 1.0))
            self.glonk_decay_mult = float(mods.get("glonk_decay", 1.0))
        else:
            self.ana_three_bias = 0.0
            self.glonk_decay_mult = 1.0
        self.passive_progress_hp_base = self.max_hp

    def passive_dynamic_damage_bonus(self, game=None):
        b=0.0; K=set(self.passive_keys); n=self.passive_upgrade_count
        if "genius_1" in K:b+=min(.06,n*.02)
        if "genius_2" in K:b+=min(.12,n*.03)
        if "genius_3" in K:b+=min(.20,n*.04)
        if "prodigy" in K:b+=min(.18,n*.03)
        if self.passive_dash_buff_timer>0 and "ghostly" in K:b+=.10
        if game is not None and getattr(game,"domain_active",False) and self.in_domain(game) and "broken_limiter" in K:b+=.10
        return b

    def passive_total_damage_bonus(self, game=None):
        return max(-.90,min(.60,self.passive_static.get("damage",0.0)+self.passive_dynamic_damage_bonus(game)))

    def passive_ally_damage_mult(self):
        return max(.10,1.0+self.passive_ally_damage)

    def passive_ally_damage_reduction(self):
        return .03 if "leader_3" in self.passive_keys else 0.0

    def passive_on_upgrade(self, game):
        self.passive_upgrade_count += 1
        if "prodigy" in self.passive_keys and self.passive_upgrade_count<=6 and self.character not in ("Sans","Glonk 100% Power"):
            grow=self.passive_progress_hp_base*.02
            self.max_hp += grow  # nao cura automaticamente
            if getattr(game,"game_mode","normal")=="extinction" and getattr(game,"extinction_hp_cap",None) is not None:
                game.extinction_hp_cap=min(game.extinction_hp_cap,self.hp)

    def passive_on_wave_clear(self, game):
        self.passive_wave_count += 1
        K=set(self.passive_keys); per=cap=0.0
        if "diligent_1" in K: per,cap=.02,.10
        elif "diligent_2" in K: per,cap=.03,.18
        elif "diligent_3" in K: per,cap=.04,.28
        if per>0 and self.character not in ("Sans","Glonk 100% Power"):
            before=min(cap,max(0,self.passive_wave_count-1)*per); after=min(cap,self.passive_wave_count*per)
            if after>before:self.max_hp += self.passive_progress_hp_base*(after-before)
        if self.passive_wave_heal>0:
            self.heal(self.max_hp*self.passive_wave_heal,game)

    def in_domain(self, game):
        return game.domain_active and self.pos.distance_to(game.domain_center) <= game.domain_radius

    def vasco_damage_multiplier(self):
        # 0% = 20% do dano base; 100% = 190% (quase o dobro).
        return 0.20 + 1.70 * clamp(self.vasco_bet_level / 100.0, 0.0, 1.0)

    def vasco_start_jackpot(self, game):
        if self.character != "Vasco" or self.vasco_jackpot_timer > 0:
            return
        # O Jackpot NAO cura HP. Ele apenas torna Vasco imortal por 8s.
        self.vasco_jackpot_timer = self.vasco_jackpot_duration
        self.vasco_jackpot_used_this_wave = True
        self.vasco_bet_level = 100.0
        game.domain_active = False
        game.domain_timer = 0.0
        game.domain_charge = 0.0
        if getattr(game, "domain_clash_active", False):
            game.domain_clash_active = False
        game.domain_message_timer = 0.0
        game.flash_screen = max(game.flash_screen, 0.18)
        game.shake = max(game.shake, S(16))
        game.damage_texts.append(DamageText("JACKPOT!", pygame.Vector2(self.pos), VASCO_NEON, 1.25))
        game.spawn_particles(self.pos, VASCO_NEON, 32)
        AUDIO.play("domain", 1.0, 250)

    def vasco_roll_attack(self, game):
        if self.character != "Vasco":
            return True
        forced_positive = bool(game.domain_active and game.player.character == "Vasco")
        old = self.vasco_bet_level

        # Fora do Dominio existem 3 resultados com a mesma chance:
        # PERDER: -10 a -15 | NEUTRO: 0 | GANHAR: +10.
        # Dentro de I JUST HIT THE JACKPOT todo ataque e obrigatoriamente GANHAR.
        if forced_positive:
            result = "win"
        elif self.vasco_marked_chip:
            r=random.random(); result = "win" if r < 0.50 else ("neutral" if r < 0.75 else "lose")
        else:
            roll = random.randrange(3)
            result = ("lose", "neutral", "win")[roll]

        if result == "win":
            gain=10.0
            if self.vasco_sevens:
                self.vasco_win_streak += 1
                if self.vasco_win_streak >= 3:
                    self.vasco_win_streak=0; gain += 20.0
            self.vasco_bet_level = min(100.0, self.vasco_bet_level + gain)
            msg = ("SEQUENCIA! " if gain>10 else "GANHOU ") + f"+{int(self.vasco_bet_level-old)}%"
            color = VASCO_NEON
        elif result == "lose":
            if self.vasco_sevens: self.vasco_win_streak=0
            loss = random.randint(10, 15)
            self.vasco_bet_level = max(0.0, self.vasco_bet_level - loss)
            msg = f"PERDEU -{int(old-self.vasco_bet_level)}%"
            color = RED
        else:
            if self.vasco_sevens: self.vasco_win_streak=0
            msg = "NEUTRO"
            color = GRAY

        game.damage_texts.append(DamageText(msg, pygame.Vector2(self.pos), color, 0.55))
        if forced_positive and self.vasco_bet_level >= 100.0:
            self.vasco_start_jackpot(game)
        return result == "win"

    def vasco_wave_start(self):
        if self.character == "Vasco":
            self.vasco_took_damage_this_wave = False
            self.vasco_jackpot_used_this_wave = False

    def vasco_wave_clear(self, game):
        if self.character != "Vasco":
            return
        if self.divine_vasco:
            full_hp = self.hp >= self.max_hp - 0.001
            clean_wave = not self.vasco_took_damage_this_wave
            # Jackpot nao pode ser usado para farmar adaptacao do Leme.
            if not self.vasco_jackpot_used_this_wave and (full_hp or clean_wave):
                old = self.vasco_dharma_reduction
                self.vasco_dharma_reduction = min(0.70, self.vasco_dharma_reduction + 0.05)
                if self.vasco_dharma_reduction > old:
                    txt = "ADAPTACAO COMPLETA" if self.vasco_dharma_reduction >= 0.70 else f"DHARMA -{int(self.vasco_dharma_reduction*100)}% DANO"
                    game.damage_texts.append(DamageText(txt, pygame.Vector2(self.pos), DIVINE_BLUE, 1.0))
                    game.spawn_particles(self.pos, DIVINE_BLUE, 14)
        self.vasco_took_damage_this_wave = False
        self.vasco_jackpot_used_this_wave = False

    def use_hank_artillery(self, game):
        if self.character != HANK_KEY or game.domain_active or game.domain_charge < 100:
            return False
        game.domain_charge = 0
        game.shake = max(game.shake, S(12))
        AUDIO.play("domain", 0.92, 180)
        game.damage_texts.append(DamageText("ARTILHARIA AGUIA", pygame.Vector2(self.pos), RED, 1.0))
        game.hank_artillery_queue = []
        top = S(165)
        bottom = H - S(335)
        for i in range(10):
            pos = pygame.Vector2(random.randint(S(90), W-S(90)), random.randint(top+S(40), bottom-S(40)))
            game.hank_artillery_queue.append({"pos": pos, "timer": 0.45 + 0.2*i, "radius": S(155), "done": False})
        return True

    def lira_end_domain(self, game):
        if self.character!=LIRA_KEY: return
        if self.lira_life_bonus>0:
            self.max_hp=max(1.0,self.max_hp-self.lira_life_bonus); self.hp=min(self.hp,self.max_hp); self.lira_life_bonus=0.0
        self.lira_domain_buffs.clear()
        for e in getattr(game,"enemies",[]): e.lira_domain_stats=set()

    def spend_stamina(self, amount):
        if self.character == "Vasco" and self.vasco_jackpot_timer > 0:
            return True
        if self.stamina >= amount:
            self.stamina -= amount
            self.stamina_regen_delay = 0.55
            return True
        if self.blood_debt:
            missing = amount - self.stamina
            hp_cost = max(1.0, missing * 1.25)
            if self.hp > hp_cost + 1:
                self.stamina = 0
                self.hp -= hp_cost
                self.stamina_regen_delay = 0.55
                return True
        return False

    def recover_stamina(self, amount, game=None):
        old = self.stamina
        if game is not None and self.character == "Sans" and getattr(game, "bad_time_active", False):
            amount *= 0.20
        cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
        self.stamina = clamp(self.stamina + amount, 0, cap)
        if game and self.stamina > old:
            game.damage_texts.append(DamageText("+" + str(int(self.stamina-old)) + " STA", pygame.Vector2(self.pos), CYAN))

    def heal(self, amount, game=None):
        if game and (getattr(game, "healing_locked", False) or getattr(game,"game_mode","normal")=="extinction"):
            return
        old = self.hp
        amount *= 1.0 + 0.04 * SAVE.get("healing_level", 0)
        self.hp = clamp(self.hp + amount, 0, self.max_hp)
        if game and self.hp > old:
            game.damage_texts.append(DamageText("+" + str(int(self.hp-old)) + " HP", pygame.Vector2(self.pos), GREEN))

    def sukuna_finger_damage_multiplier(self):
        return 1.0 + 0.20 * min(20, max(0, int(getattr(self, "sukuna_fingers", 0))))

    def gain_sukuna_finger(self, game):
        if self.character != SUKUNA_KEY or self.sukuna_fingers >= 20:
            return False
        if self.sukuna_finger_hp_base is None:
            self.sukuna_finger_hp_base = float(self.max_hp)
        self.sukuna_fingers = min(20, self.sukuna_fingers + 1)
        gained_hp = self.sukuna_finger_hp_base * 0.05
        # Soma incremental: preserva HP obtido por upgrades/passivas progressivas da run.
        self.max_hp += gained_hp
        # O novo HP ganho pelo dedo entra cheio; nao e uma cura percentual do HP antigo.
        self.hp = min(self.max_hp, self.hp + gained_hp)
        game.damage_texts.append(DamageText(f"DEDO DO SUKUNA {self.sukuna_fingers}/20", pygame.Vector2(self.pos), SUKUNA_HAIR, 1.2))
        AUDIO.play("unlock", 0.85, 160)
        return True

    def use_sukuna_ult_tap(self, game):
        """Toque curto no ULT: marca/confirma o Fuuga. Segurar e tratado separadamente."""
        if self.character != SUKUNA_KEY or getattr(game,"sukuna_cutscene_active",False) or getattr(game,"sukuna_destruction_active",False):
            return False
        if game.domain_active or game.domain_charge < 100:
            return False
        if not getattr(game,"sukuna_ult_marked",False):
            return game.mark_sukuna_ult()
        game.domain_charge = 0
        return game.start_sukuna_cutscene()

    def activate_sukuna_domain(self, game):
        if self.character != SUKUNA_KEY or game.domain_active or game.domain_charge < 100:
            return False
        if getattr(game,"sukuna_cutscene_active",False) or getattr(game,"sukuna_destruction_active",False):
            return False
        game.domain_charge = 0
        game.sukuna_ult_marked = False
        AUDIO.play("domain", 1.0, 250)
        game.shake = max(game.shake, S(18)); game.flash_screen=max(game.flash_screen,0.10)
        game.domain_active = True
        game.domain_center = pygame.Vector2(W/2, (S(165)+H-S(335))/2)
        game.domain_radius = math.hypot(W, H) * 1.15
        game.domain_duration = 8.0
        game.domain_timer = 8.0
        game.domain_name = "SANTUARIO MALEVOLENTE"
        game.domain_message_timer = 1.65
        game.sukuna_domain_tick_cd = 0.0
        game.attack_held = False
        # Troca imediata para o tema do Santuário. O sync_music o mantém durante o dominio
        # e volta para a trilha normal assim que os 8 segundos acabam.
        if AUDIO.music_on:
            AUDIO._try_external_music("sukuna_domain", AUDIO.music_volume)
        if game.mode == "arena" and not is_beta_character(self.character):
            SAVE["total_domains"] = SAVE.get("total_domains", 0) + 1
            if SAVE["total_domains"] >= 100: game.unlock_achievement("domain_100")
            if SAVE["total_domains"] >= 500: game.unlock_achievement("domain_500")
            save_data(SAVE); game.check_progress_achievements(); game.add_mission_progress("domains", 1)
        return True

    def effective_damage_mult(self, game, enemy=None, source="generic", distance=None):
        m = self.damage_mult * game.player_event_damage_mult
        passive_bonus=self.passive_total_damage_bonus(game)
        if enemy is not None and isinstance(enemy, Boss):
            passive_bonus += self.passive_static.get("boss_damage",0.0)
        if getattr(game,"domain_active",False) and self.in_domain(game):
            passive_bonus += self.passive_domain_damage
        # Regra V15: todos os percentuais de dano de passiva se somam primeiro; teto final +60%.
        passive_bonus=max(-.90,min(.60,passive_bonus))
        m *= max(0.10,1.0+passive_bonus)
        if getattr(game,"game_mode","normal")=="rogue" and getattr(game,"rogue_rule",None)=="glass": m*=1.35
        if SAVE.get("cheat_infinite_damage", False):
            m *= 1000000.0
        if self.overclock and self.stamina >= self.max_stamina * 0.80:
            m *= 1.20
        if self.predator_timer > 0:
            m *= 1.25
        if self.god_not_watching and self.hp <= self.max_hp * 0.20:
            m *= 1.65
        if self.character == "Vasco":
            m *= self.vasco_damage_multiplier()
        if self.character == SUKUNA_KEY:
            m *= self.sukuna_finger_damage_multiplier()
        if self.character == LIRA_KEY and game.domain_active and "strength" in self.lira_domain_buffs:
            m *= 1.70
        if self.giant_hunter and enemy is not None:
            if isinstance(enemy, Boss) or enemy.kind == "tank" or enemy.elite == "giant":
                m *= 1.40
        if self.character == "Ana" and source in ("staff", "staff_miniana") and self.ana_blind_spot and distance is not None and distance >= S(360):
            m *= 1.45
        if self.character == "Ana" and source in ("staff", "staff_miniana") and self.ana_causal_eye and distance is not None and distance >= S(430):
            m *= 1.30
        if self.character == "Kayk" and source in ("dual_pistol", "soul_shot"):
            m *= self.kayk_pistol_bonus
        if self.character == "Kevyn" and source in ("sword", "execute"):
            m *= self.kevyn_sword_bonus
            if self.kevyn_human_wall:
                m *= 1.0 + min(0.35, self.max_hp / 900.0)
        if self.character == "Ycaro" and source == "shotgun" and distance is not None:
            if self.ycaro_point_blank and distance <= S(175):
                m *= 1.55
            if self.ycaro_sawed_off and distance <= S(205):
                m *= 1.35
            if "EXECUCAO BALISTICA" in game.synergies and distance <= S(185):
                m *= 1.35
            if self.ycaro_no_too_close and self.in_domain(game) and distance <= S(230):
                m *= 1.40
        if self.character == "Pedro" and source == "pineapple":
            m *= self.pedro_damage_mult
        if self.character == "Ruan" and source == "ruan_dash":
            m *= self.ruan_dash_damage_mult
        if self.character == "Colosso do Caos" and source == "father_wave":
            m *= self.father_damage_mult
            if isinstance(enemy, Boss):
                m *= self.father_boss_weapon_mult
                if self.father_boss_bonus:
                    m *= 1.55
        # POWER UPS 2.0 — multiplicadores contextuais.
        if self.hybrid_inertia_timer > 0:
            m *= 1.25
        if self.hybrid_resonant_domain and getattr(game,"domain_active",False) and self.in_domain(game):
            m *= 1.15
        if self.character == "Vasco" and self.vasco_high_stakes and self.vasco_bet_level >= 70:
            m *= 1.30
        if self.character == "Kevyn" and self.kevyn_one_vs_hundred and source in ("sword","execute"):
            nearby=sum(1 for e in game.enemies if not e.dead and e.pos.distance_to(self.pos)<=S(330))
            m *= 1.0 + min(0.60, nearby*0.06)
        if self.character == HANK_KEY and self.hank_madness_combat and source in ("sword","hank_knives") and getattr(game,"domain_active",False):
            m *= 1.50
        if self.character == "Sans" and self.sans_karmic_judgement and source == "sans_blaster":
            m *= 1.50
        if self.character == RIP_INDRA_KEY and source in ("rip_ttk","rip_wave","rip_wave_explosion"):
            if self.in_domain(game): m *= 2.0
        return m

    def take_damage(self, amount, game):
        if self.character == "Vasco" and self.vasco_jackpot_timer > 0:
            # Imortalidade real: nao reduz HP, nao cura e nao gera adaptacao do Dharma.
            if self.vasco_immune_text_cd <= 0:
                game.damage_texts.append(DamageText("JACKPOT - IMORTAL", pygame.Vector2(self.pos), VASCO_NEON, 0.45))
                self.vasco_immune_text_cd = 0.35
            return False
        if SAVE.get("cheat_immortal", False):
            game.damage_texts.append(DamageText("IMORTAL", pygame.Vector2(self.pos), YELLOW, 0.55))
            return False
        # Sans: ataques sao evitados consumindo Estamina. Zerou = fica exausto e o proximo acerto pode matar.
        if self.character == "Sans":
            if self.invuln > 0 or self.dash_time > 0:
                return False
            if self.shield > 0:
                self.shield -= 1
                game.damage_texts.append(DamageText("BLOCK", pygame.Vector2(self.pos), BLUE))
                self.invuln = 0.30
                return False
            if not self.sans_exhausted and self.stamina > 0:
                cost = min(self.stamina, self.sans_dodge_cost)
                self.stamina = max(0.0, self.stamina-cost)
                self.stamina_regen_delay = 0.45
                side = pygame.Vector2(-self.facing.y, self.facing.x)
                if random.random() < 0.5: side *= -1
                self.pos += side * S(42)
                self.pos.x = clamp(self.pos.x, self.radius, W-self.radius)
                self.pos.y = clamp(self.pos.y, S(205)+self.radius, H-S(335)-self.radius)
                self.invuln = 0.22
                game.damage_texts.append(DamageText("MISS", pygame.Vector2(self.pos), WHITE, 0.7))
                game.spawn_particles(self.pos, WHITE, 7)
                if self.stamina <= 0.001:
                    self.stamina = 0
                    self.sans_exhausted = True
                    game.damage_texts.append(DamageText("EXAUSTO!", pygame.Vector2(self.pos), RED, 1.0))
                return False
            amount = max(1.0, amount)
        # Dominio do Kevyn: enquanto ele permanecer dentro da area, nada o fere.
        if self.character == "Kevyn" and self.in_domain(game):
            game.damage_texts.append(DamageText("INTOCAVEL", pygame.Vector2(self.pos), BLUE))
            return False
        if self.invuln > 0 or self.dash_time > 0:
            return False
        if self.shield > 0:
            self.shield -= 1
            AUDIO.play("shield", 0.75, 60)
            game.damage_texts.append(DamageText("BLOCK", pygame.Vector2(self.pos), BLUE))
            game.shake = max(game.shake, S(5))
            self.invuln = 0.35
            return False
        impossible_hit = game.mode == "arena" and getattr(game, "difficulty", "easy") == "impossible"
        if impossible_hit:
            # IMPOSSIVEL: se o golpe realmente entrou, o valor e sempre 10% do HP maximo.
            # Dash, escudo, Dominio do Kevyn e outras formas de EVITAR o acerto continuam valendo.
            amount = self.max_hp * 0.10
            stamina_drain = self.max_stamina * 0.075
            self.stamina = max(0.0, self.stamina - stamina_drain)
            self.stamina_regen_delay = max(self.stamina_regen_delay, 0.8)
            game.damage_texts.append(DamageText(f"-{int(stamina_drain)} STA", pygame.Vector2(self.pos)+pygame.Vector2(0,S(34)), CYAN, 0.65))
        else:
            if self.character == "Kevyn" and self.kevyn_immovable and self.still_timer >= 0.8:
                amount *= 0.55
            if self.no_brakes:
                amount *= 1.25
            amount *= max(0.55, 1.0 - 0.03 * SAVE.get("armor_level", 0))
            amount *= max(0.625, 1.0 - 0.015 * self.evo_resistance)
        if self.character == "Vasco" and self.divine_vasco and self.vasco_dharma_reduction > 0:
            amount *= max(0.30, 1.0 - self.vasco_dharma_reduction)
        if self.character == LIRA_KEY and game.domain_active and "resistance" in self.lira_domain_buffs:
            amount *= 0.50
        if self.character == "Vasco":
            self.vasco_took_damage_this_wave = True
        amount *= max(0.0,1.0-self.passive_damage_reduction)
        self.hp -= amount
        if getattr(game,"game_mode","normal") == "extinction":
            if getattr(game,"extinction_hp_cap",None) is None:
                game.extinction_hp_cap = self.hp
            else:
                game.extinction_hp_cap = min(game.extinction_hp_cap, self.hp)
        if self.forge_ana and self.ana_forge_cd <= 0 and self.hp > 0:
            d = pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
            game.summons.append(MiniAna(self.pos-d*S(30), self.base_damage*1.35, 0, 1, self.ana_miniana_speed, self.ana_blast_mult, self.ana_reality_error))
            self.ana_forge_cd = 5.0
            game.damage_texts.append(DamageText("CAJADO REAGIU!", pygame.Vector2(self.pos), PINK, 0.8))
        if hasattr(game, "record_clash_hurt"):
            game.record_clash_hurt(amount)
        AUDIO.play("hurt", 0.72, 120)
        if self.eternal_combo:
            game.combo //= 2
            game.combo_timer = 2.0 if game.combo else 0
        else:
            game.combo = 0
            game.combo_timer = 0
        game.damage_texts.append(DamageText("-" + str(int(amount)) + " HP", pygame.Vector2(self.pos), RED))
        game.spawn_particles(self.pos, RED, 12)
        game.shake = max(game.shake, S(12))
        # V14 FINAL: dano recebido nao concede mais i-frame automatico.
        # Invulnerabilidade de Dash, escudo, revive e habilidades continua existindo separadamente.
        if self.hp <= 0:
            if self.character==HISOKA_KEY and not self.hisoka_revived:
                self.hisoka_revived=True
                hp_ratio=0.80 if self.hisoka_show_must_go_on else 0.62
                self.max_hp *= 1.25 if self.hisoka_show_must_go_on else 1.15
                self.base_damage *= 1.35 if self.hisoka_show_must_go_on else 1.22
                self.base_speed *= 1.18
                self.color=HISOKA_REVIVE_COLOR
                self.hp=self.max_hp*hp_ratio; self.stamina=self.max_stamina; self.invuln=1.6
                game.damage_texts.append(DamageText("BOMBEIA-GUM!",pygame.Vector2(self.pos),HISOKA_REVIVE_COLOR,1.4))
                game.spawn_particles(self.pos,HISOKA_REVIVE_COLOR,32); AUDIO.play("revive",1.0); game.flash_screen=max(game.flash_screen,0.18)
                return False
            if self.character=="Glonk" and self.glonk_last_one and not getattr(self,"glonk_last_one_used",False):
                self.glonk_last_one_used=True; self.hp=1; self.invuln=max(self.invuln,1.0)
                game.damage_texts.append(DamageText("GLONK, O ULTIMO",pygame.Vector2(self.pos),GREEN,1.0)); return False
            if self.passive_fatal_save and not self.passive_protagonist_used:
                self.passive_protagonist_used=True
                self.hp=1
                self.invuln=max(self.invuln,1.0)
                game.damage_texts.append(DamageText("PROTAGONISTA! 1 HP",pygame.Vector2(self.pos),RED,1.0))
                return False
            # EXTINCAO: nem Segunda Barra / Um Ultimo Jogo podem recuperar HP.
            if getattr(game,"game_mode","normal") != "extinction" and not self.revive_used and (self.second_bar or self.one_last_game):
                self.revive_used = True
                self.hp = self.max_hp * 0.40
                self.stamina = self.max_stamina
                self.invuln = 1.4
                if self.one_last_game:
                    game.healing_locked = True
                    self.damage_mult *= 1.25
                # explosao de renascimento
                for e in list(game.enemies):
                    if not e.dead and e.pos.distance_to(self.pos) <= S(260):
                        old = game.current_damage_kind
                        game.current_damage_kind = "revive"
                        e.damage(self.base_damage * 3.2, game, self.pos)
                        game.current_damage_kind = old
                AUDIO.play("revive", 0.90)
                game.damage_texts.append(DamageText("SEGUNDA CHANCE!", pygame.Vector2(self.pos), YELLOW, 1.1))
                game.flash_screen = 0.22
                return False
            self.hp = 0
            game.end_run()
        return True

    def _auto_aim(self, game, domain_only=False, max_range=None):
        candidates = [e for e in game.enemies if not e.dead]
        if domain_only:
            candidates = [e for e in candidates if e.pos.distance_to(game.domain_center) <= game.domain_radius]
        if max_range is not None:
            candidates = [e for e in candidates if e.pos.distance_to(self.pos) <= max_range]
        if not candidates:
            return False
        target = min(candidates, key=lambda e: e.pos.distance_to(self.pos))
        d = target.pos - self.pos
        if d.length_squared() > 0:
            self.facing = d.normalize()
            return True
        return False

    def summon_divine_dogs(self, game):
        if self.character != "Potential Man":
            return False
        alive=[x for x in game.potential_summons if isinstance(x,DivineDog) and not x.dead]
        if alive:
            game.damage_texts.append(DamageText("CAES JA ESTAO ATIVOS", pygame.Vector2(self.pos), WHITE, 0.75))
            return False
        if self.potential_dog_cd > 0:
            game.damage_texts.append(DamageText(f"CAES {self.potential_dog_cd:.1f}s", pygame.Vector2(self.pos), RED, 0.75))
            return False
        if not self.spend_stamina(8):
            game.damage_texts.append(DamageText("SEM ESTAMINA", pygame.Vector2(self.pos), RED, 0.65))
            return False
        side=pygame.Vector2(-self.facing.y,self.facing.x) if self.facing.length_squared() else pygame.Vector2(0,1)
        game.potential_summons.append(DivineDog(self.pos+side*S(45),self,1))
        game.potential_summons.append(DivineDog(self.pos-side*S(45),self,-1))
        game.damage_texts.append(DamageText("CAES DIVINOS!",pygame.Vector2(self.pos),WHITE,0.9))
        AUDIO.play("unlock",0.55,120)
        return True

    def potential_frog_attack(self, game):
        if self.character != "Potential Man" or self.attack_cd > 0 or game.state != "playing":
            return False
        if not self.spend_stamina(5):
            return False
        self.attack_cd = 0.72
        d = pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
        d = d.normalize()
        self.potential_frog_dir = pygame.Vector2(d)
        self.potential_frog_fx = 0.18
        length = S(235)
        half_angle = math.radians(24)
        cos_limit = math.cos(half_angle)
        hit_any = False
        old=game.current_damage_kind; game.current_damage_kind="potential_frogs"
        for e in list(game.enemies):
            if e.dead:
                continue
            to_e=e.pos-self.pos; dist=to_e.length()
            if dist <= length + e.radius and (dist <= self.radius+e.radius+S(18) or (dist>0.001 and (to_e/dist).dot(d) >= cos_limit)):
                dmg=self.base_damage*0.90*self.effective_damage_mult(game,e,"potential_frogs",dist)
                e.damage(dmg,game,self.pos)
                hit_any=True
        maho=getattr(game,"mahoraga",None)
        if maho is not None and not maho.dead:
            to_m=maho.pos-self.pos; md=to_m.length()
            if md <= length+maho.radius and (md <= self.radius+maho.radius+S(18) or (md>0.001 and (to_m/md).dot(d) >= cos_limit)):
                dmg=self.base_damage*0.90*self.effective_damage_mult(game,None,"potential_frogs",md)
                maho.take_damage(dmg,game,self.pos,from_player=True)
                hit_any=True
        game.current_damage_kind=old
        if hit_any:
            game.register_combo_hit()
            game.domain_charge_primary_hit(20.0)
        AUDIO.play("hit",0.38,70)
        return True

    def has_divine_attack_hold(self):
        # V14: somente Longinus captura o ATK para hold.
        # Kevyn volta a repetir ataques segurando ATK; Pedro usa hold no DASH.
        return self.divine_ana

    def divine_pull(self, game):
        radius=S(620)
        for e in game.enemies:
            if e.dead: continue
            d=self.pos-e.pos; dist=d.length()
            if 1<dist<=radius: e.pos += d.normalize()*min(S(260),dist*0.55)
        game.spawn_particles(self.pos,DIVINE_BLUE,28); game.damage_texts.append(DamageText("AZUL: ATRAIR",pygame.Vector2(self.pos),DIVINE_BLUE,0.8))

    def divine_repel(self, game):
        radius=S(620)
        for e in game.enemies:
            if e.dead: continue
            d=e.pos-self.pos; dist=d.length()
            if dist<=radius:
                if dist<1: d=pygame.Vector2(1,0)
                e.pos += d.normalize()*S(300)
        game.projectiles=[pr for pr in game.projectiles if not (pr.owner=="enemy" and pr.pos.distance_to(self.pos)<=radius)]
        game.spawn_particles(self.pos,RED,30); game.damage_texts.append(DamageText("VERMELHO: REPELIR",pygame.Vector2(self.pos),RED,0.8))

    def divine_purple_burst(self, game):
        if game.domain_charge < 100: return False
        game.domain_charge=0
        radius=S(520)*self.father_domain_radius_mult
        game.divine_burst_fx={"timer":0.55,"total":0.55,"center":pygame.Vector2(self.pos),"radius":radius}
        old=game.current_damage_kind; game.current_damage_kind="divine_purple"
        for e in list(game.enemies):
            if not e.dead and e.pos.distance_to(self.pos)<=radius+e.radius:
                e.hp=0; e.die(game)
        game.current_damage_kind=old
        game.projectiles=[pr for pr in game.projectiles if not (pr.owner=="enemy" and pr.pos.distance_to(self.pos)<=radius)]
        game.shake=max(game.shake,S(25)); game.flash_screen=max(game.flash_screen,0.16)
        game.damage_texts.append(DamageText("ROXO: COLAPSO",pygame.Vector2(self.pos),PURPLE,1.0))
        return True

    def divine_kayk_reset(self, game):
        if self.kayk_builder_wave_used == game.wave: return False
        self.kayk_builder_wave_used=game.wave
        # EXTINCAO bloqueia TODA recuperacao de HP, inclusive a arma Divina.
        if getattr(game,"game_mode","normal") == "extinction":
            self.stamina=self.max_stamina
            game.damage_texts.append(DamageText("EXTINCAO: HP NAO VOLTA",pygame.Vector2(self.pos),RED,1.0))
            return True
        self.hp=self.max_hp; self.stamina=self.max_stamina
        game.damage_texts.append(DamageText("BIG BUILDER: RESET",pygame.Vector2(self.pos),DIVINE_BLUE,1.0)); AUDIO.play("heal",0.9)
        return True

    def plant_divine_pineapple(self, game):
        d=self.facing.normalize() if self.facing.length_squared() else pygame.Vector2(1,0)
        game.planted_pineapples.append(PlantedPineapple(self.pos+d*S(95),max(3.0,self.base_damage*0.55)))
        game.damage_texts.append(DamageText("ABACAXI PLANTADO",pygame.Vector2(self.pos),YELLOW,0.7))

    def divine_ruan_teleport(self, game, move_dir):
        if self.dash_cd>0 or self.dash_time>0 or not self.spend_stamina(5): return False
        origin=pygame.Vector2(self.pos)
        if move_dir.length_squared()==0: move_dir=pygame.Vector2(self.facing)
        if move_dir.length_squared()==0: move_dir=pygame.Vector2(1,0)
        d=move_dir.normalize()
        # Dash comum percorre aproximadamente base_speed*3.2*0.18; teleporte = 2x essa distancia.
        teleport_distance=self.base_speed*3.2*0.18*2.0
        self.pos += d*teleport_distance
        self.pos.x=clamp(self.pos.x,self.radius,W-self.radius); self.pos.y=clamp(self.pos.y,S(205)+self.radius,H-S(335)-self.radius)
        self.invuln=max(self.invuln,0.30); self.dash_cd=max(self.dash_cd,0.72)
        self._divine_ruan_friend_if_empty(game, origin)
        game.spawn_particles(self.pos,PURPLE,18); AUDIO.play("dash",0.8)
        return True

    def _divine_ruan_friend_if_empty(self, game, spawn_pos=None):
        # Manto do Monarca: so cria um Amigo pelo Dash se nao houver nenhum Amigo normal vivo.
        if not self.divine_ruan or any(not s.dead and not s.guardian for s in game.servants):
            return False
        targets=[e for e in game.enemies if not e.dead and not isinstance(e,TrainingDummy)]
        if targets:
            source=min(targets,key=lambda e:e.pos.distance_to(self.pos))
        else:
            class _MonarchFriendSeed:
                max_hp=95.0; radius=S(25); speed=S(175); contact_damage=12.0; color=GREEN; kind="chaser"; elite=None
            source=_MonarchFriendSeed()
        pos=pygame.Vector2(spawn_pos if spawn_pos is not None else self.pos)
        game.servants.append(RuanServant(pos,source,self,guardian=False))
        game.damage_texts.append(DamageText("AMIGO DO MANTO",pygame.Vector2(pos),GREEN,0.8))
        return True

    def uses_special_attack_hold(self):
        return self.character in (RIP_INDRA_KEY, HISOKA_KEY)

    def finish_special_attack_hold(self, game):
        if self.character == RIP_INDRA_KEY:
            held=self.rip_hold_time; self.rip_hold_time=0.0
            if held >= self.rip_hold_threshold: self.rip_charged_attack(game,held)
            else: self.rip_click_attack(game)
            return
        if self.character == HISOKA_KEY:
            held=self.hisoka_hold_time; self.hisoka_hold_time=0.0
            if held >= self.hisoka_hold_threshold: self.hisoka_charged_attack(game,held)
            else: self.hisoka_click_attack(game)

    def rip_click_attack(self,game):
        if self.attack_cd>0 or game.state!="playing" or not self.spend_stamina(4): return
        inside=self.in_domain(game); self.attack_cd=0.13 if inside else 0.40
        rng=S(190)*self.rip_range_mult; angle_limit=math.cos(math.radians(86)); hit_any=False
        for e in list(game.enemies):
            if e.dead: continue
            v=e.pos-self.pos; dist=v.length()
            if dist<=rng+e.radius and (dist<=self.radius+e.radius+S(40) or (dist>0.001 and (v/dist).dot(self.facing)>=angle_limit)):
                old=game.current_damage_kind; game.current_damage_kind="rip_ttk"
                e.damage(self.base_damage*1.15*self.rip_sword_damage_mult*self.effective_damage_mult(game,e,"rip_ttk",dist),game,self.pos)
                game.current_damage_kind=old; hit_any=True
        if hit_any: game.register_combo_hit(); game.domain_charge_primary_hit(20.0)
        self.rip_click_fx = 0.16
        self.rip_click_dir = pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
        game.spawn_particles(self.pos,RIP_INDRA_COLOR,12); AUDIO.play("kevyn_sword",0.72,80)

    def rip_charged_attack(self,game,held):
        if self.attack_cd>0 or game.state!="playing" or not self.spend_stamina(8): return
        max_charge=1.45 if self.rip_triple_authority else self.rip_charge_max
        ratio=clamp((held-self.rip_hold_threshold)/max(0.1,max_charge-self.rip_hold_threshold),0.0,1.0)
        inside=self.in_domain(game); self.attack_cd=0.22 if inside else 0.72
        d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0); base=math.atan2(d.y,d.x)
        speed=S(1120 if self.rip_admin_rage else 780); dmg=self.base_damage*self.rip_sword_damage_mult*(1.05+1.95*ratio)
        for off in (-0.20,0.0,0.20):
            sd=vec_from_angle(base+off); pr=Projectile(self.pos+sd*S(46),sd*speed,dmg,"player",S(13),RIP_INDRA_COLOR,2.2*self.rip_range_mult,1 if self.rip_triple_authority else 0)
            pr.kind="rip_wave"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=20.0/3.0; pr.domain_charge_uses_left=1; pr.rip_explosive=self.rip_admin_rage
            game.projectiles.append(pr)
        AUDIO.play("ycaro_shotgun",0.62,90); game.shake=max(game.shake,S(8))

    def hisoka_click_attack(self,game):
        if self.attack_cd>0 or game.state!="playing" or not self.spend_stamina(4): return
        self.attack_cd=0.42 if not self.hisoka_revived else 0.30
        d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0); base=math.atan2(d.y,d.x)
        if self.hisoka_revived:
            count=8 if self.hisoka_show_must_go_on else 6
            offsets=[(i-(count-1)/2)*0.105 for i in range(count)]
            for off in offsets:
                pr=HisokaCardProjectile(self,vec_from_angle(base+off),self.base_damage*0.58,spider=True,return_mult=1.0)
                pr.domain_charge_raw=20.0/count; game.projectiles.append(pr)
        else:
            count=3 if self.hisoka_card_trick else 2
            offsets=[0.0] if count==1 else [(-0.09 if count==2 else -0.13), (0.09 if count==2 else 0.0)] + ([] if count==2 else [0.13])
            for off in offsets:
                pr=HisokaCardProjectile(self,vec_from_angle(base+off),self.base_damage*0.72,return_mult=1.0)
                pr.domain_charge_raw=20.0/count; game.projectiles.append(pr)
        AUDIO.play("kayk_dual",0.45,75)

    def hisoka_charged_attack(self,game,held):
        if self.attack_cd>0 or game.state!="playing" or not self.spend_stamina(7): return
        ratio=clamp((held-self.hisoka_hold_threshold)/max(0.1,self.hisoka_charge_max-self.hisoka_hold_threshold),0.0,1.0)
        self.attack_cd=0.62 if not self.hisoka_revived else 0.44
        d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
        pr=HisokaCardProjectile(self,d,self.base_damage*(1.35+1.25*ratio),charged=True,return_mult=1.0)
        if self.hisoka_paralyzing_joker: pr.radius*=1.5
        game.projectiles.append(pr); AUDIO.play("kayk_dual",0.62,85)

    def finish_attack_hold(self, game):
        if not self.has_divine_attack_hold(): return
        if not self.divine_attack_triggered:
            self.attack(game)
        self.divine_attack_hold=0.0; self.divine_attack_triggered=False; self.longinus_next_threshold=2.0

    def finish_parry_hold(self, game):
        if self.divine_kevyn and not self.divine_parry_triggered: self.parry(game)
        self.divine_parry_hold=0.0; self.divine_parry_triggered=False

    def finish_domain_hold(self, game):
        if self.character == HANK_KEY:
            held = self.hank_domain_hold
            triggered = self.hank_domain_triggered
            self.hank_domain_hold = 0.0
            self.hank_domain_triggered = False
            if not triggered and held > 0:
                self.use_hank_artillery(game)
            return
        if self.character == SUKUNA_KEY:
            held = self.sukuna_domain_hold
            triggered = self.sukuna_domain_triggered
            self.sukuna_domain_hold = 0.0
            self.sukuna_domain_triggered = False
            if not triggered and held > 0:
                self.use_sukuna_ult_tap(game)
            return
        if self.divine_kevyn and not self.divine_domain_triggered: self.expand_domain(game)
        self.divine_domain_hold=0.0; self.divine_domain_triggered=False

    def finish_dash_hold(self, game):
        if (self.divine_ruan or self.divine_kayk or self.divine_pedro or self.divine_kevyn) and not self.divine_dash_triggered:
            self.dash(game,game.get_move_dir())
        self.divine_dash_hold=0.0; self.divine_dash_triggered=False

    def attack(self, game):
        if self.character == "Glonk":
            return
        ycaro_domain = self.character == "Ycaro" and self.in_domain(game)
        if self.attack_cd > 0 and not ycaro_domain:
            return
        if game.state != "playing":
            return
        if self.character == "Sans" and self.sans_exhausted:
            return
        if self.character == RIP_INDRA_KEY:
            self.rip_click_attack(game); return
        if self.character == HISOKA_KEY:
            self.hisoka_click_attack(game); return

        # Sans beta: parado = osso teleguiado no alvo mais proximo; andando = golpe corpo a corpo.
        # Blaster nao e mais carregado pelo ATK; existe apenas no botao BLAST dedicado.
        if self.character == "Sans":
            if self.attack_cd > 0:
                return
            if self.is_moving:
                if not self.spend_stamina(3):
                    return
                self.attack_cd = 0.38
                rng = S(132)
                angle_limit = math.cos(math.radians(78))
                hit_any = False
                for e in list(game.enemies):
                    if e.dead: continue
                    to_e = e.pos-self.pos; dist = to_e.length()
                    if dist <= rng + e.radius:
                        close = dist <= self.radius+e.radius+S(30)
                        if close or (dist>0.001 and (to_e/dist).dot(self.facing) >= angle_limit):
                            old=game.current_damage_kind; game.current_damage_kind="sans_melee_bone"
                            e.damage(self.base_damage*1.15*self.effective_damage_mult(game,e,"sans_melee",dist), game, self.pos)
                            game.current_damage_kind=old; hit_any=True
                maho=getattr(game,"mahoraga",None)
                if maho is not None and not maho.dead:
                    to_m=maho.pos-self.pos; md=to_m.length()
                    if md <= rng+maho.radius and (md <= self.radius+maho.radius+S(30) or (md>0.001 and (to_m/md).dot(self.facing)>=angle_limit)):
                        maho.take_damage(self.base_damage*1.15*self.effective_damage_mult(game,None,"sans_melee",md),game,self.pos,from_player=True)
                        hit_any=True
                if hit_any:
                    game.register_combo_hit()
                    game.domain_charge_primary_hit(20.0)
                self.sans_melee_fx = 0.16
                self.sans_melee_dir = pygame.Vector2(self.facing)
            else:
                if not self.spend_stamina(4):
                    return
                targets=[e for e in game.enemies if not e.dead]
                if targets:
                    target=min(targets,key=lambda e:e.pos.distance_to(self.pos))
                    d=target.pos-self.pos
                    if d.length_squared()>0:
                        self.facing=d.normalize()
                d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
                pr=Projectile(self.pos+d*S(35), d*S(820), self.base_damage*self.projectile_bonus, "player", S(9), WHITE, 2.3, self.projectile_pierce)
                pr.kind="sans_bone"; pr.origin=pygame.Vector2(self.pos)
                pr.domain_charge_raw=20.0; pr.domain_charge_uses_left=1
                game.projectiles.append(pr)
                self.attack_cd=0.56
            AUDIO.play("kevyn_sword",0.45,70)
            return

        # Potential Man: toque no ATK mira automaticamente no inimigo mais proximo e usa Sapos.
        # Segurar 3s continua invocando os Caes Divinos.
        if self.character == "Potential Man":
            self._auto_aim(game)
            self.potential_frog_attack(game)
            return

        # Lira Solis, A C#nsur#: ataque personalizado usando censured.png.
        if self.character == LIRA_KEY:
            if not self.spend_stamina(4): return
            intellect_buff=game.domain_active and "intelligence" in self.lira_domain_buffs
            self.attack_cd=0.25 if intellect_buff else 0.52
            d=game.attack_direction() if hasattr(game,"attack_direction") else pygame.Vector2(self.facing)
            if d.length_squared()==0: d=pygame.Vector2(1,0)
            d=d.normalize(); self.facing=pygame.Vector2(d)
            pr=Projectile(self.pos+d*S(38),d*S(900 if intellect_buff else 720),self.base_damage*0.65*self.projectile_bonus,"player",S(18) if self.lira_thick_bar else S(12),LIRA_COLOR,3.6 if intellect_buff else 2.2,self.projectile_pierce)
            pr.kind="lira_censor"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=20.0; pr.domain_charge_uses_left=1; game.projectiles.append(pr)
            AUDIO.play("kayk_dual",0.34,70); return

        # Vasco, O Apostador Incansavel: resolve UMA aposta por ataque e dispara
        # uma rajada de 3 projeteis redondos. Cada projetil que realmente acerta
        # concede +2 de Nivel da Aposta, independentemente do resultado do sorteio.
        if self.character == "Vasco":
            if not self.spend_stamina(5):
                return
            self.attack_cd = 0.42
            self.vasco_roll_attack(game)
            d = game.attack_direction() if hasattr(game, "attack_direction") else pygame.Vector2(self.facing)
            if d.length_squared() == 0:
                d = pygame.Vector2(1,0)
            d = d.normalize(); self.facing = pygame.Vector2(d)
            base_a = math.atan2(d.y,d.x)
            # Dano dividido para a nova rajada nao triplicar o DPS antigo.
            for off in (-0.12, 0.0, 0.12):
                shot_d = vec_from_angle(base_a+off)
                pr = Projectile(self.pos+shot_d*S(36), shot_d*S(780), self.base_damage*self.projectile_bonus*0.42,
                                "player", S(10), VASCO_GREEN, 2.4, self.projectile_pierce)
                pr.kind = "vasco_bet"
                pr.origin = pygame.Vector2(self.pos)
                pr.domain_charge_raw = 20.0 / 3.0
                pr.domain_charge_uses_left = 1
                game.projectiles.append(pr)
            AUDIO.play("kayk_dual", 0.48, 75)
            return

        if self.character == HANK_KEY:
            if game.domain_active and game.player.character == HANK_KEY:
                if not self.spend_stamina(4):
                    return
                self.attack_cd = 0.28
                rng = S(120)
                hit_any = False
                angle_limit = math.cos(math.radians(84))
                for e in list(game.enemies):
                    if e.dead:
                        continue
                    to_e = e.pos - self.pos
                    dist = to_e.length()
                    if dist <= rng + e.radius:
                        close = dist <= self.radius + e.radius + S(28)
                        if close or (dist > 0.001 and (to_e/dist).dot(self.facing) >= angle_limit):
                            old=game.current_damage_kind; game.current_damage_kind="hank_knives"
                            e.damage(self.base_damage*0.82*self.effective_damage_mult(game,e,"sword",dist), game, self.pos)
                            game.current_damage_kind=old; hit_any=True
                maho = getattr(game, "mahoraga", None)
                if maho is not None and not maho.dead:
                    to_m = maho.pos-self.pos; md=to_m.length()
                    if md <= rng+maho.radius and (md <= self.radius+maho.radius+S(28) or (md>0.001 and (to_m/md).dot(self.facing)>=angle_limit)):
                        maho.take_damage(self.base_damage*0.82*self.effective_damage_mult(game,None,"sword",md),game,self.pos,from_player=True)
                        hit_any=True
                if hit_any:
                    game.register_combo_hit()
                    game.slash_fx = 0.14
                AUDIO.play("kevyn_sword",0.45,65)
                return
            if self.still_timer < self.hank_charge_required:
                return
            if not self.spend_stamina(6):
                return
            self.attack_cd = 1.55 if self.hank_bolt_cycle else 2.0
            d = game.attack_direction() if hasattr(game, "attack_direction") else pygame.Vector2(self.facing)
            if d.length_squared() == 0:
                d = pygame.Vector2(1,0)
            d = d.normalize(); self.facing = pygame.Vector2(d)
            shell_r=max(S(18),int(self.radius*0.80))
            spawn_pos = self.pos+d*(self.radius+shell_r+S(8))
            pr = Projectile(spawn_pos, d*S(720), self.base_damage*1.20*self.projectile_bonus, "player", shell_r, (210,210,210), 3.2, 0)
            pr.kind="hank_shell"; pr.origin=pygame.Vector2(self.pos); pr.hank_explosion_radius=S(155)*(1.25 if self.hank_high_caliber else 1.0); pr.hank_explosion_damage=self.base_damage*1.05*self.projectile_bonus; pr.hank_confirmed_target=self.hank_confirmed_target
            pr.domain_charge_raw=20.0; pr.domain_charge_uses_left=1
            # V15 Hank: alcance real = 65% da distancia ate a borda na direcao da mira.
            range_end = hank_range_endpoint(spawn_pos, d)
            pr.hank_range_origin = pygame.Vector2(spawn_pos)
            pr.hank_max_distance = max(S(40), spawn_pos.distance_to(range_end))
            game.projectiles.append(pr)
            AUDIO.play("hank_cannon",0.92,100); game.shake=max(game.shake,S(11)); game.flash_screen=max(game.flash_screen,0.035)
            return

        # Sukuna: corte de espada/energia com leitura igual a do Kevyn, mas lancado na direcao que ele esta olhando.
        if self.character == SUKUNA_KEY:
            if not self.spend_stamina(4):
                return
            self.attack_cd = 0.42
            d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
            d=d.normalize()
            slash_speed=S(1030) if self.sukuna_dismantle else S(860)
            slash_radius=S(25) if self.sukuna_dismantle else S(18)
            slash_life=2.75 if self.sukuna_dismantle else 2.25
            pr=Projectile(self.pos+d*S(42), d*slash_speed, self.base_damage*self.projectile_bonus, "player", slash_radius, SUKUNA_SLASH, slash_life, self.projectile_pierce)
            pr.kind="sukuna_slash"; pr.origin=pygame.Vector2(self.pos)
            pr.domain_charge_raw=20.0; pr.domain_charge_uses_left=1
            game.projectiles.append(pr)
            self.sukuna_slash_fx=0.14
            AUDIO.play("kevyn_sword",0.72,75)
            return

        # Vinicius 13: projetil vermelho retangular, levemente teleguiado e com espalhamento em ate 3 alvos.
        if self.character == "Vinicius 13":
            if not self.spend_stamina(4): return
            self.attack_cd=0.46
            d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
            pr=Projectile(self.pos+d*S(34),d*S(700),self.base_damage*0.72*self.projectile_bonus,"player",S(8),RED,2.3,0)
            pr.kind="vinicius_bolt"; pr.origin=pygame.Vector2(self.pos); pr.vinicius_child=False; pr.domain_charge_raw=20.0; pr.domain_charge_uses_left=1; game.projectiles.append(pr)
            game.damage_texts.append(DamageText(random.choice(VINICIUS_QUOTES),pygame.Vector2(self.pos.x,self.pos.y-S(70)),RED,1.05))
            AUDIO.play("kayk_dual",0.42,80); return

        # Strikada Egoista: Chute Direto na direcao atual. A bola comeca reta e, ao acertar,
        # procura o proximo alvo ate o limite de inimigos. Dentro do Dominio, o quique nao acaba.
        if self.character == "Strikada Egoísta":
            if not self.spend_stamina(7):
                return
            self.attack_cd = 2.0
            base_d = pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
            base_a = math.atan2(base_d.y, base_d.x)
            count = 1 + self.strikada_extra_balls
            offsets = [0.0] if count == 1 else [-0.10, 0.10]
            for off in offsets:
                d = vec_from_angle(base_a + off)
                pr = Projectile(self.pos + d*S(38), d*S(620), self.base_damage*self.projectile_bonus,
                                "player", S(16), (125,220,255), 6.0, 0)
                pr.kind = "strikada_ball"
                if self.hybrid_kinetic_rebound: pr.strikada_hits_left=getattr(pr,"strikada_hits_left",self.strikada_bounces)+1; pr.vel*=1.15
                if self.strikada_next_infinite:
                    pr.strikada_hits_left=999; pr.strikada_force_infinite=True; self.strikada_next_infinite=False
                pr.wall_bounce = True
                pr.origin = pygame.Vector2(self.pos)
                pr.domain_charge_raw = 20.0 / max(1, count)
                pr.domain_charge_uses_left = 1
                pr.strikada_hits_left = self.strikada_bounces
                pr.strikada_homing = self.strikada_homing
                pr.strikada_kill_explosion = self.strikada_kill_explosion
                game.projectiles.append(pr)
            AUDIO.play("ycaro_shotgun",0.42,80)
            return

        # Glonk 100% Power: o golpe tem mira propria, independente da direcao de movimento.
        # Alcance dobrado: 155 -> 310. A direcao visual/colisao fica congelada no alvo do clique.
        if self.character == "Glonk 100% Power":
            candidates=[e for e in game.enemies if not e.dead]
            maho=getattr(game,"mahoraga",None)
            target=min(candidates,key=lambda e:e.pos.distance_to(self.pos)) if candidates else None
            if target is None and maho is not None and not maho.dead:
                target=maho
            if target is not None:
                aim=pygame.Vector2(target.pos)-self.pos
                if aim.length_squared()>0:
                    self.glonk_power_dir=aim.normalize()
            elif self.facing.length_squared()>0:
                self.glonk_power_dir=pygame.Vector2(self.facing).normalize()
            aim_dir=self.glonk_power_dir if self.glonk_power_dir.length_squared()>0 else pygame.Vector2(1,0)
            self.attack_cd = 0.46
            self.glonk_power_fx = 0.36
            rng = S(420) if self.glonk_industrial_tongue else S(310)
            hit_any = False
            cos_limit=math.cos(math.radians(84 if self.glonk_industrial_tongue else 72))
            glonk_attack_mult = 75.0 if (self.glonk_101_power and self.glonk_101_ready) else 1.0
            for e in list(game.enemies):
                if e.dead:
                    continue
                to_e = e.pos-self.pos
                dist = to_e.length()
                if dist <= rng + e.radius and (dist<=0.001 or (to_e/dist).dot(aim_dir)>=cos_limit):
                    old_kind=game.current_damage_kind; game.current_damage_kind="glonk_100"
                    e.damage(self.base_damage*glonk_attack_mult*self.effective_damage_mult(game,e,"glonk_100",dist),game,self.pos)
                    game.current_damage_kind=old_kind
                    hit_any=True
            if maho is not None and not maho.dead:
                to_m=maho.pos-self.pos; md=to_m.length()
                if md <= rng+maho.radius and (md<=0.001 or (to_m/md).dot(aim_dir)>=cos_limit):
                    maho.take_damage(self.base_damage*self.effective_damage_mult(game,None,"glonk_100",md),game,self.pos,from_player=True)
                    hit_any=True
            if hit_any:
                if self.glonk_101_power and self.glonk_101_ready:
                    self.glonk_101_ready=False; game.damage_texts.append(DamageText("101% POWER!!!",pygame.Vector2(self.pos),YELLOW,0.8))
                game.register_combo_hit()
                game.domain_charge_primary_hit(20.0)
            AUDIO.play("hit",0.20,80)
            return

        if self.character == "Ycaro":
            if ycaro_domain:
                self._auto_aim(game, domain_only=True)
            elif self.ycaro_hunter:
                self._auto_aim(game, max_range=S(420))

        # Kevyn: espada e execucao.
        if self.character == "Kevyn":
            marked = [e for e in game.enemies if not e.dead and e.marked and self.pos.distance_to(e.pos) <= S(115) * self.kevyn_sword_range]
            if marked and self.spend_stamina(max(1, 2-self.kevyn_sword_cost_reduction)):
                target = min(marked, key=lambda e: self.pos.distance_to(e.pos))
                game.current_damage_kind = "execute"
                target.hp = 0
                target.die(game)
                game.current_damage_kind = None
                self.recover_stamina(15 + self.execute_bonus, game)
                game.domain_charge_primary_hit(20.0)
                AUDIO.play("execute", 0.95)
                game.damage_texts.append(DamageText("EXECUCAO!", pygame.Vector2(target.pos), YELLOW))
                game.shake = max(game.shake, S(18))
                self.attack_cd = 0.32
                return
            if not self.spend_stamina(max(1, 2-self.kevyn_sword_cost_reduction)):
                return
            kevyn_domain_evo = self.in_domain(game) and self.domain_evolution
            if self.forge_kevyn:
                parry_radius = S(170) * self.kevyn_sword_range
                for pr in game.projectiles:
                    if pr.owner == "enemy" and pr.pos.distance_to(self.pos) <= parry_radius:
                        pr.owner = "player"
                        pr.vel *= -1.35
                        pr.damage *= 1.35
                        pr.color = BLUE
                        pr.parry_reflected = True
                game.damage_texts.append(DamageText("PARRY DA LAMINA", pygame.Vector2(self.pos), BLUE, 0.45))
            self.attack_cd = 0.16 if kevyn_domain_evo else 0.28
            crowd_range=1.0
            if self.kevyn_one_vs_hundred:
                nearby=sum(1 for e in game.enemies if not e.dead and e.pos.distance_to(self.pos)<=S(330)); crowd_range += min(0.50,nearby*0.05)
            rng = S(122) * self.kevyn_sword_range * (1.20 if kevyn_domain_evo else 1.0) * crowd_range
            angle_limit = math.cos(math.radians(72))
            hit_any = False
            for e in list(game.enemies):
                if e.dead:
                    continue
                to_e = e.pos - self.pos
                dist = to_e.length()
                if dist <= rng + e.radius:
                    # Muito perto/encostado = sempre entra na hitbox da espada.
                    close_hit = dist <= self.radius + e.radius + S(34)
                    facing_hit = close_hit
                    if not close_hit and dist > 0.001:
                        facing_hit = (to_e / dist).dot(self.facing) >= angle_limit
                    if facing_hit:
                        dmg = self.base_damage * self.effective_damage_mult(game, e, "sword", dist)
                        if self.kevyn_absolute_parry_ready: dmg *= 2.5
                        passive_crit_hit = random.random() < self.crit_chance
                        if passive_crit_hit:
                            dmg *= self.crit_damage_mult
                            game.damage_texts.append(DamageText("CRIT!", pygame.Vector2(e.pos), YELLOW))
                        game.current_damage_kind = "sword"
                        was_alive=not e.dead
                        e.damage(dmg, game, self.pos)
                        if passive_crit_hit and was_alive and e.dead: game.award_passive_critical_kill(e)
                        game.current_damage_kind = None
                        self.recover_stamina(self.stamina_on_hit, game)
                        hit_any = True
            maho=getattr(game,"mahoraga",None)
            if maho is not None and not maho.dead:
                to_m=maho.pos-self.pos; md=to_m.length()
                if md <= rng+maho.radius:
                    close_hit = md <= self.radius+maho.radius+S(34)
                    facing_hit = close_hit or (md>0.001 and (to_m/md).dot(self.facing)>=angle_limit)
                    if facing_hit:
                        dmg=self.base_damage*self.effective_damage_mult(game,None,"sword",md)
                        maho.take_damage(dmg,game,self.pos,from_player=True)
                        hit_any=True
            if self.divine_kevyn:
                d=self.facing.normalize() if self.facing.length_squared() else pygame.Vector2(1,0)
                pr=Projectile(self.pos+d*S(55),d*S(920),self.base_damage*0.72*self.projectile_bonus,"player",S(18),DIVINE_BLUE,1.25,2+self.projectile_pierce)
                pr.kind="kevyn_divine_slash"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=0.0; pr.domain_charge_uses_left=0; game.projectiles.append(pr)
            if hit_any and self.kevyn_second_cut and random.random()<0.25:
                old=game.current_damage_kind; game.current_damage_kind="sword"
                for e in list(game.enemies):
                    if e.dead: continue
                    to_e=e.pos-self.pos; dist=to_e.length()
                    if dist<=rng+e.radius and (dist<=self.radius+e.radius+S(34) or (dist>0.001 and (to_e/dist).dot(self.facing)>=angle_limit)):
                        bonus=1.25 if (self.kevyn_absolute_parry_ready and "DOIS CORTES, UM INSTANTE" in game.synergies) else 1.0
                        e.damage(self.base_damage*bonus*self.effective_damage_mult(game,e,"sword",dist),game,self.pos,minimal_fx=True)
                game.current_damage_kind=old; game.damage_texts.append(DamageText("SEGUNDO CORTE",pygame.Vector2(self.pos),WHITE,0.45))
            if hit_any and self.kevyn_absolute_parry_ready:
                self.kevyn_absolute_parry_ready=False
            AUDIO.play("kevyn_sword", 0.72, 90)
            game.slash_fx = 0.12
            if hit_any:
                game.register_combo_hit()
                game.domain_charge_primary_hit(20.0)
            return

        # Ana: cajado. Dano-base foi reduzido em 50%; cooldown normal agora e 2s.
        # Cada ataque invoca aleatoriamente 1 a 3 Mini-Anas ao redor dela, usando os vertices de um triangulo.
        if self.character == "Ana":
            if not self.spend_stamina(9):
                return
            in_dom = self.in_domain(game)
            self.attack_cd = 1.0 if in_dom else 2.0
            roll = random.random()
            bias = getattr(self, "ana_three_bias", 0.0)
            if roll < 0.34 - bias*0.20:
                count = 1
            elif roll < 0.72 - bias*0.35:
                count = 2
            else:
                count = 3
            if self.ana_double_shot:
                count = min(3, count + 1)
            if self.ana_pocket_army:
                count = min(3, count + 1)
            base_angle = math.atan2(self.facing.y, self.facing.x) - math.pi/2
            triangle_angles = [base_angle, base_angle + math.tau/3, base_angle + 2*math.tau/3]
            # 1 e 2 invocacoes ocupam vertices diferentes; 3 fecha o triangulo inteiro.
            chosen = triangle_angles if count == 3 else (triangle_angles[:1] if count == 1 else [triangle_angles[0], triangle_angles[2]])
            for i, ang in enumerate(chosen):
                spawn = self.pos + vec_from_angle(ang) * S(42)
                summon = MiniAna(
                    spawn,
                    self.base_damage * 1.55 * self.projectile_bonus * self.summon_power_mult,
                    i, count,
                    self.ana_miniana_speed * self.summon_power_mult,
                    self.ana_blast_mult,
                    self.ana_reality_error,
                )
                self.ana_spawn_counter += 1
                if self.ana_unstable_reality and self.ana_spawn_counter % 5 == 0:
                    summon.damage *= 2.0; summon.radius = int(summon.radius*1.65); summon.blast_radius *= 1.40; summon.is_giant=True
                    game.damage_texts.append(DamageText("MINI-ANA GIGANTE!",pygame.Vector2(spawn),PINK,0.7))
                game.summons.append(summon)
            AUDIO.play("ana_staff", 0.72, 140)
            game.damage_texts.append(DamageText(f"MINI-ANAS x{count}!", pygame.Vector2(self.pos), PINK))
            return

        # Kayk: duas pistolas. Cada ataque dispara um par de balas.
        if self.character == "Kayk":
            if not self.spend_stamina(5):
                return
            kayk_domain = self.in_domain(game)
            self.attack_cd = 0.18 if kayk_domain else 0.24
            if kayk_domain:
                self._auto_aim(game, domain_only=True)
            elif self.kayk_two_triggers:
                weak=[e for e in game.enemies if not e.dead and e.hp<=e.max_hp*0.40]
                if weak:
                    t=min(weak,key=lambda e:e.pos.distance_to(self.pos)); d=t.pos-self.pos
                    if d.length_squared()>0: self.facing=d.normalize(); game.aim_vector=pygame.Vector2(self.facing)
            pairs = 1 + self.kayk_extra_pair
            aim_d = game.attack_direction() if hasattr(game,"attack_direction") else pygame.Vector2(self.facing)
            base_a = math.atan2(aim_d.y, aim_d.x)
            # Dentro do Dominio: cada rajada ganha +1 bala e os projeteis ficam 35% mais rapidos.
            offsets = (-0.075, 0.0, 0.075) if kayk_domain else (-0.055, 0.055)
            kayk_shot_speed = 1.35 if kayk_domain else 1.0
            divine_extra_shots = 4 if self.divine_kayk else 0
            kayk_total_shots = max(1, pairs*len(offsets) + divine_extra_shots)
            kayk_domain_raw_each = 20.0 / kayk_total_shots
            for pair in range(pairs):
                pair_shift = (pair - (pairs-1)/2) * 0.08
                for off in offsets:
                    d = vec_from_angle(base_a + off + pair_shift)
                    pr = Projectile(self.pos + d*S(36), d*S(790)*kayk_shot_speed, self.base_damage*0.78*self.projectile_bonus, "player", S(7), PURPLE, 2.0, self.projectile_pierce + self.kayk_soul_pierce)
                    pr.kind = "dual_pistol"
                    pr.forge_kayk = self.forge_kayk
                    pr.origin = pygame.Vector2(self.pos)
                    pr.domain_charge_raw = kayk_domain_raw_each
                    pr.domain_charge_uses_left = 1
                    game.projectiles.append(pr)
            if self.divine_kayk:
                # +1 bala frontal e tres tiros curtos para tras/lados.
                for ang,life in ((base_a,1.2),(base_a+math.pi/2,0.48),(base_a-math.pi/2,0.48),(base_a+math.pi,0.48)):
                    d=vec_from_angle(ang)
                    pr=Projectile(self.pos+d*S(34),d*S(760),self.base_damage*0.72*self.projectile_bonus,"player",S(8),DIVINE_BLUE,life,self.projectile_pierce+self.kayk_soul_pierce)
                    pr.kind="dual_pistol"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=kayk_domain_raw_each; pr.domain_charge_uses_left=1; game.projectiles.append(pr)
            if self.kayk_crossfire and random.random()<0.45:
                for side in (-math.pi/2, math.pi/2):
                    d=vec_from_angle(base_a+side); pr=Projectile(self.pos+d*S(34),d*S(690),self.base_damage*0.55*self.projectile_bonus,"player",S(7),PURPLE,1.35,self.projectile_pierce)
                    pr.kind="dual_pistol"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=0.0; pr.domain_charge_uses_left=0; game.projectiles.append(pr)
            AUDIO.play("kayk_dual", 0.70, 70)
            return

        # Pedro: abacaxi bumerangue. No Dominio cada ataque forma um X.
        if self.character == "Pedro":
            if not self.spend_stamina(6):
                return
            self.attack_cd = 0.52
            domain = self.in_domain(game)
            shots = []
            if domain:
                shots = [vec_from_angle(math.pi/4 + i*math.pi/2) for i in range(4)]
                if self.pedro_x_destiny:
                    shots += [vec_from_angle(i*math.pi/2) for i in range(4)]
            else:
                aim_d = game.attack_direction() if hasattr(game,"attack_direction") else pygame.Vector2(self.facing)
                base = math.atan2(aim_d.y, aim_d.x)
                count = 1 + self.pedro_extra_boomerangs
                for i in range(count):
                    spread = (i-(count-1)/2) * 0.22
                    shots.append(vec_from_angle(base+spread))
            pedro_domain_raw_each = 20.0 / max(1, len(shots)*2)
            for d in shots:
                boom = BoomerangProjectile(
                    self, d, self.base_damage*self.projectile_bonus,
                    self.pedro_speed_mult, self.pedro_range_mult,
                    self.pedro_return_hit, self.pedro_explosive, self.pedro_crown,
                )
                if self.forge_pedro:
                    boom.radius = int(boom.radius * 1.50)
                boom.divine_pedro = self.divine_pedro
                boom.domain_charge_raw = pedro_domain_raw_each
                boom.domain_charge_uses_left = 2
                game.projectiles.append(boom)
            AUDIO.play("kayk_dual", 0.42, 90)
            return

        # Ruan: o proprio ataque e uma investida. Abates DIRETOS viram aliados.
        if self.character == "Ruan":
            if not self.spend_stamina(6):
                return
            self.attack_cd = 0.46
            self.ruan_attack_time = 0.29 if self.ruan_necro_step else 0.21
            self.ruan_attack_dir = self.facing.normalize() if self.facing.length_squared() else pygame.Vector2(1, 0)
            self.ruan_hit_ids = set()
            self.ruan_domain_charge_awarded = False
            self.invuln = max(self.invuln, 0.15)
            AUDIO.play("dash", 0.72, 80)
            return

        # Colosso do Caos: golpe circular grande ao redor dele.
        if self.character == "Colosso do Caos":
            if not self.spend_stamina(10):
                return
            self.attack_cd = 0.82
            radius = S(270) * self.father_radius_mult * (1.0 + self.father_next_radius_bonus)
            self.father_next_radius_bonus = 0.0
            game.father_wave_fx_timer = 0.48
            game.father_wave_fx_total = 0.48
            game.father_wave_fx_center = pygame.Vector2(self.pos)
            game.father_wave_fx_radius = radius
            hit_any = False; father_hits=0; father_kills_before=game.kills
            old = game.current_damage_kind
            game.current_damage_kind = "father_wave"
            for e in list(game.enemies):
                if not e.dead and e.pos.distance_to(self.pos) <= radius + e.radius:
                    dmg = self.base_damage * self.effective_damage_mult(game, e, "father_wave", e.pos.distance_to(self.pos))
                    e.damage(dmg, game, self.pos)
                    hit_any = True; father_hits += 1
            maho=getattr(game,"mahoraga",None)
            if maho is not None and not maho.dead and maho.pos.distance_to(self.pos) <= radius+maho.radius:
                dmg=self.base_damage*self.effective_damage_mult(game,None,"father_wave",maho.pos.distance_to(self.pos))
                maho.take_damage(dmg,game,self.pos,from_player=True)
                hit_any=True
            game.current_damage_kind = old
            if self.father_growing_authority and father_hits>0:
                self.father_next_radius_bonus=min(0.45,father_hits*0.035)
            if self.father_repeat_slap and father_hits>0:
                game.delayed_blasts.append({"timer":1.0,"pos":pygame.Vector2(self.pos),"radius":radius,"damage":self.base_damage*0.45*self.father_damage_mult,"color":WHITE})
            if self.father_paternal_sentence and game.kills-father_kills_before>=3:
                game.delayed_blasts.append({"timer":0.18,"pos":pygame.Vector2(self.pos),"radius":radius*1.12,"damage":self.base_damage*0.70*self.father_damage_mult,"color":YELLOW})
            if self.father_clear_projectiles:
                game.projectiles = [pr for pr in game.projectiles if not (pr.owner == "enemy" and pr.pos.distance_to(self.pos) <= radius)]
            game.spawn_particles(self.pos, WHITE, 24)
            game.shake = max(game.shake, S(13))
            AUDIO.play("boss", 0.48, 180)
            if hit_any:
                game.register_combo_hit()
                game.domain_charge_primary_hit(20.0)
            return

        # Ycaro: shotgun.
        if self.character == "Ycaro":
            if not self.divine_ycaro and not self.spend_stamina(7):
                return
            self.attack_cd = (0.018 if ycaro_domain else 0.29) if self.divine_ycaro else (0.035 if ycaro_domain else 0.58)
            if self.divine_ycaro:
                self.speed_buff=max(self.speed_buff,0.85)
            aim_d = game.attack_direction() if hasattr(game,"attack_direction") else pygame.Vector2(self.facing)
            base_a = math.atan2(aim_d.y, aim_d.x)
            pellets = 5 + self.ycaro_extra_pellets
            if self.ycaro_heavy_lead: pellets=max(3,int(math.ceil(pellets*0.60)))
            if ycaro_domain and self.domain_evolution:
                pellets += 1
            if ycaro_domain and self.ycaro_no_too_close:
                pellets += 2
            spread = 0.26 if self.ycaro_sawed_off else 0.20
            if self.ycaro_wounded_hunter:
                spread *= 0.45 + 0.55*clamp(self.hp/max(1,self.max_hp),0,1)
            offsets = [0] if pellets == 1 else [(-spread + (2*spread)*i/(pellets-1)) for i in range(pellets)]
            ycaro_domain_raw_each = 20.0 / max(1, len(offsets))
            for off in offsets:
                d = vec_from_angle(base_a + off)
                pellet_damage=self.base_damage*0.56*self.projectile_bonus*(1.70 if self.ycaro_heavy_lead else 1.0)
                pellet_radius=S(13) if self.ycaro_heavy_lead else S(7)
                pr = Projectile(self.pos + d*S(35), d*S(690)*self.ycaro_pellet_speed,
                                pellet_damage, "player", pellet_radius, ORANGE,
                                0.82*self.ycaro_pellet_speed, self.projectile_pierce)
                pr.kind = "shotgun"
                pr.origin = pygame.Vector2(self.pos)
                pr.domain_charge_raw = ycaro_domain_raw_each
                pr.domain_charge_uses_left = 1
                game.projectiles.append(pr)
            if self.ycaro_twelve_barrels and random.random()<0.30:
                for off in offsets:
                    d=vec_from_angle(base_a+off+0.035); pr=Projectile(self.pos+d*S(35),d*S(690)*self.ycaro_pellet_speed,self.base_damage*0.48*self.projectile_bonus*(1.70 if self.ycaro_heavy_lead else 1.0),"player",S(13) if self.ycaro_heavy_lead else S(7),ORANGE,0.82*self.ycaro_pellet_speed,self.projectile_pierce)
                    pr.kind="shotgun"; pr.origin=pygame.Vector2(self.pos); pr.domain_charge_raw=0.0; pr.domain_charge_uses_left=0; game.projectiles.append(pr)
                game.damage_texts.append(DamageText("DOZE CANOS!",pygame.Vector2(self.pos),ORANGE,0.4))
            AUDIO.play("ycaro_shotgun", 0.78, 55)
            game.shake = max(game.shake, S(9))

    def fire_sans_blaster(self, game, auto=False):
        if self.character != "Sans" or self.sans_exhausted or self.sans_blaster_cd > 0:
            return False
        targets=[e for e in game.enemies if not e.dead]
        if targets:
            target=min(targets,key=lambda e:e.pos.distance_to(self.pos))
            d=target.pos-self.pos
            if d.length_squared()>0:
                self.facing=d.normalize()
        d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
        d=d.normalize()
        start=pygame.Vector2(self.pos)
        end=ray_to_arena_edge(start,d)
        beam_length=max(1.0,(end-start).length())
        width=S(44 if auto else 62)
        mult=1.65 if auto else 4.2
        old=game.current_damage_kind
        game.current_damage_kind="sans_blaster_auto" if auto else "sans_blaster"
        hit_any=False

        # Em waves altas um feixe pode atingir dezenas de alvos no mesmo frame.
        # O modo de FX leve reduz particulas durante esse pico para evitar engasgos no Android.
        game.mass_hit_fx=True
        try:
            for e in list(game.enemies):
                if e.dead:
                    continue
                if beam_hits_point_fast(e.pos,start,d,beam_length,width+e.radius):
                    e.damage(self.base_damage*mult*self.effective_damage_mult(game,e,"sans_blaster",e.pos.distance_to(self.pos)),game,self.pos, minimal_fx=True)
                    hit_any=True
        finally:
            game.mass_hit_fx=False
            game.current_damage_kind=old

        # Apaga projeteis no feixe usando a mesma colisao barata.
        kept=[]
        for pr in game.projectiles:
            if pr.owner=="enemy" and beam_hits_point_fast(pr.pos,start,d,beam_length,width+pr.radius):
                continue
            kept.append(pr)
        game.projectiles=kept

        fx_time=0.09 if auto else 0.15
        game.sans_blaster_fx.append({"start":start,"end":end,"width":width,"timer":fx_time,"total":fx_time})
        # Nunca acumula uma pilha de feixes visuais na tela.
        if len(game.sans_blaster_fx) > 2:
            game.sans_blaster_fx = game.sans_blaster_fx[-2:]
        self.sans_blaster_cd = 2.0 if game.bad_time_active else 15.0
        if not auto:
            game.shake=max(game.shake,S(7))
            game.flash_screen=max(game.flash_screen,0.035)
        AUDIO.play("domain" if auto else "boss",0.45 if auto else 0.62,180)
        if hit_any:
            game.register_combo_hit()
            game.domain_charge_primary_hit(20.0)
        return True

    def update_sans_charge(self, dt, game):
        # Mantido apenas por compatibilidade com saves/codigo antigo. O charge foi removido.
        return

    def reset_sans_charge(self):
        return

    def dash(self, game, move_dir):
        if self.character == "Glonk" or (self.character == "Sans" and self.sans_exhausted) or self.dash_cd > 0 or self.dash_time > 0:
            return
        dash_origin = pygame.Vector2(self.pos)
        dash_cost = 3 if self.character == "Kayk" and self.kayk_spectral_step else 5
        if self.character == "Sans" and self.sans_blue_shortcut:
            dash_cost = max(1, dash_cost-2)
        if not self.spend_stamina(dash_cost):
            return
        if move_dir.length_squared() == 0:
            move_dir = pygame.Vector2(self.facing)
        self.dash_dir = move_dir.normalize()
        special_dash = self.ana_vector_step or (self.character == "Kayk" and self.kayk_spectral_step)
        self.dash_time = 0.24 if special_dash else 0.18
        dash_cd_base = 0.50 if special_dash else 0.72
        self.dash_cd = dash_cd_base * max(0.60, 1.0 - 0.04 * SAVE.get("dash_level", 0)) * max(0.75,1.0-self.passive_dash_recharge)
        if self.character == "Sans" and self.sans_blue_shortcut:
            self.dash_cd *= 0.70
        if self.hybrid_inertia:
            self.hybrid_inertia_timer = 2.0
        if "ghostly" in self.passive_keys:self.passive_dash_buff_timer=3.0
        self.invuln = 0.27 if special_dash else 0.22
        AUDIO.play("dash", 0.58, 70)
        if self.divine_ruan:
            self._divine_ruan_friend_if_empty(game, dash_origin)

        near = any(p.owner == "enemy" and p.pos.distance_to(self.pos) < S(115) for p in game.projectiles)
        if near:
            self.recover_stamina(7, game)
            game.perfect_dodges += 1
            AUDIO.play("perfect", 0.85, 80)
            game.damage_texts.append(DamageText("PERFECT DODGE!", pygame.Vector2(self.pos), CYAN))
            # V15: Perfect Dodge nao recarrega mais Dominio; somente acertos em inimigos.
            if self.broken_time:
                game.enemy_slow_timer = max(game.enemy_slow_timer, 2.2)
        if self.ghost_dash:
            game.delayed_blasts.append({"timer":0.70, "pos":pygame.Vector2(self.pos), "radius":S(150), "damage":self.base_damage*1.2, "color":CYAN})

    def parry(self, game):
        # Sans nao possui Parry; o botao correspondente e dedicado ao Blaster.
        if self.character == "Sans":
            return
        if self.character == "Glonk" or self.parry_cd > 0:
            return
        cost = 2 if self.character == "Pedro" and self.pedro_steel_peel else 3
        if not self.spend_stamina(cost):
            return
        base_window = 0.22 if self.character == "Pedro" and self.pedro_steel_peel else 0.16
        base_cd = 0.68 if self.character == "Pedro" and self.pedro_steel_peel else 0.8
        self.parry_time = base_window + 0.006 * self.evo_parry
        self.parry_cd = base_cd * max(0.625, 1.0 - 0.015 * self.evo_parry)

    def expand_domain(self, game):
        if self.character == SUKUNA_KEY:
            self.activate_sukuna_domain(game)
            return
        if self.character == "Vasco" and self.vasco_jackpot_timer > 0:
            return
        if self.character == "Potential Man":
            if game.domain_charge < 100 or getattr(game, "mahoraga_cutscene_active", False):
                return
            alive=[x for x in game.potential_summons if isinstance(x,MahoragaSummon) and not x.dead]
            if alive:
                return
            game.domain_charge=0
            game.start_mahoraga_cutscene()
            return
        if self.character in ("Glonk", "Glonk 100% Power") or game.domain_active:
            return
        if self.character == "Sans":
            if self.sans_exhausted:
                return
            # BAD TIME pode ser usada com barra cheia OU emergencialmente abaixo de 50% de Estamina.
            if game.domain_charge < 100 and self.stamina >= self.max_stamina*0.50:
                return
            game.domain_charge=0
            game.bad_time_active=True
            game.domain_active=True
            game.domain_center=pygame.Vector2(W/2,(S(165)+H-S(335))/2)
            game.domain_radius=math.hypot(W,H)
            game.domain_duration=13.0 if self.sans_worse_time else 10.0
            game.domain_timer=game.domain_duration
            game.domain_name="BAD TIME"
            game.domain_message_timer=1.8
            game.bad_time_bone_cd=0.03 if self.sans_worse_time else 0.05
            game.bad_time_obstacle_cd=0.30
            self.sans_blaster_cd=min(self.sans_blaster_cd,0.6)
            AUDIO.play("domain",1.0,250)
            game.shake=max(game.shake,S(18)); game.flash_screen=max(game.flash_screen,0.12)
            return
        if game.domain_charge < 100:
            return
        if self.devil_pact:
            cost = self.max_hp * 0.12
            if self.hp <= cost + 1:
                return
            self.hp -= cost
        game.domain_charge = 0
        AUDIO.play("domain", 1.0, 250)
        game.shake = max(game.shake, S(16))
        game.flash_screen = max(game.flash_screen, 0.10)
        game.domain_center = pygame.Vector2(self.pos)
        # V15: raio global das Expansoes jogaveis aumentado em +50%.
        # 375 -> 562.5 antes de multiplicadores especificos do personagem.
        base_radius = S(562.5)
        if self.character == "Colosso do Caos":
            base_radius *= self.father_domain_radius_mult
        if self.character == RIP_INDRA_KEY:
            base_radius *= 1.45
        game.domain_radius = base_radius
        game.domain_duration = (8.0 + (2.0 if self.domain_evolution else 0.0)) * (1.0+self.passive_domain_duration)
        if self.hybrid_resonant_domain:
            game.domain_duration += 1.5
        if self.character == "Colosso do Caos":
            game.domain_duration = 5.5 + (1.5 if self.domain_evolution else 0.0)
        if (self.character == "Ana" and self.ana_reality_exe) or (self.character == "Kevyn" and self.kevyn_time_stops) or (self.character == "Ycaro" and self.ycaro_no_too_close) or (self.character == "Kayk" and self.kayk_thousand_souls):
            game.domain_duration += 1.5
        game.domain_active = True
        game.domain_timer = game.domain_duration
        game.domain_name = self.domain_name
        if game.mode == "arena" and not is_beta_character(self.character):
            SAVE["total_domains"] = SAVE.get("total_domains", 0) + 1
            if SAVE["total_domains"] >= 100: game.unlock_achievement("domain_100")
            if SAVE["total_domains"] >= 500: game.unlock_achievement("domain_500")
            save_data(SAVE); game.check_progress_achievements(); game.add_mission_progress("domains", 1)
        game.domain_message_timer = 1.65
        game.attack_held = False
        game.kayk_domain_fire_cd = 0.0
        self.stamina = min(self.max_stamina * (1.30 if self.beyond_limit else 1.0), self.stamina + self.max_stamina * 0.35)

        # Kevyn: evolucao devolve projeteis que ja estavam dentro do circulo.
        if self.character == "Kevyn" and self.kevyn_time_stops:
            for pr in game.projectiles:
                if pr.owner == "enemy" and game.is_in_domain(pr.pos):
                    pr.owner = "player"
                    pr.vel *= -1.5
                    pr.damage *= 2.0
                    pr.color = BLUE
                    pr.parry_reflected = True

        if self.character == LIRA_KEY:
            game.start_lira_domain_choice()
            return

        if self.character == HANK_KEY:
            game.domain_radius = int(game.domain_radius * 1.30)
            game.hank_domain_active = True
            game.hank_domain_trapped_ids = {e.id for e in game.enemies if not e.dead and game.is_in_domain(e.pos)}
            self.hank_cannon_planted = True
            self.hank_artillery_cd = 0.55
            game.hank_cannon_pos = pygame.Vector2(game.domain_center)
            self.recover_stamina(self.max_stamina*0.25, game)
            game.damage_texts.append(DamageText("SEJA BEM VINDO (OU NAO)", pygame.Vector2(self.pos), WHITE, 1.0))

        if self.character == HISOKA_KEY:
            # AS DO BARALHO: uma carta teleguiada para cada alvo que estava dentro na ativacao.
            targets=[e for e in game.enemies if not e.dead and game.is_in_domain(e.pos)]
            for e in targets:
                d=e.pos-self.pos
                if d.length_squared()==0: d=vec_from_angle(random.random()*math.tau)
                boss=isinstance(e,Boss)
                dmg=self.base_damage*4.2 if boss else max(self.base_damage*3.0,e.max_hp*0.90)
                pr=Projectile(self.pos+d.normalize()*S(38),d.normalize()*S(760),dmg,"player",S(12),HISOKA_REVIVE_COLOR if self.hisoka_revived else HISOKA_COLOR,3.0,0)
                pr.kind="hisoka_domain_card"; pr.origin=pygame.Vector2(self.pos); pr.hisoka_target=e; pr.domain_charge_raw=0.0; pr.domain_charge_uses_left=0
                game.projectiles.append(pr)
            game.damage_texts.append(DamageText("AS DO BARALHO!",pygame.Vector2(self.pos),HISOKA_COLOR,1.0))

        # Ruan: invoca um guardiao-BOSS que existe ate o fim da Expansao.
        if self.character == "Ruan":
            self.heal(self.max_hp * 0.28, game)
            self.recover_stamina(self.max_stamina * 0.45, game)
            guardian = RuanServant(self.pos + pygame.Vector2(S(70), 0), self, self, guardian=True)
            game.servants.append(guardian)
            game.ruan_guardian = guardian
            game.damage_texts.append(DamageText("GUARDIAO INVOCADO!", pygame.Vector2(self.pos), CYAN, 1.1))

        # Colosso do Caos jogavel: tudo que estiver DENTRO da area e sentenciado na hora.
        if self.character == "Colosso do Caos":
            old = game.current_damage_kind
            game.current_damage_kind = "father_domain"
            for e in list(game.enemies):
                if not e.dead and game.is_in_domain(e.pos):
                    if isinstance(e, GlonkEnemy):
                        continue
                    e.hp = 0
                    e.die(game)
            game.current_damage_kind = old
            if self.father_domain_refill:
                self.hp = self.max_hp
                self.stamina = self.max_stamina
            game.damage_texts.append(DamageText("SENTENCA ABSOLUTA", pygame.Vector2(self.pos), WHITE, 1.1))

        # Se um boss ja abriu seu Dominio e os circulos se encontram, comeca o Clash.
        for e in game.enemies:
            if isinstance(e, Boss) and not e.dead and e.domain_active and game.domains_overlap(e):
                game.start_domain_clash(e)
                break

    def update(self, dt, game, move_dir):
        lira_cooldown_rate = 2.0 if (self.character==LIRA_KEY and game.domain_active and "intelligence" in self.lira_domain_buffs) else 1.0
        passive_attack_rate=max(0.10,1.0+self.passive_attack_speed)/max(0.75,1.0-self.passive_attack_recharge)
        self.attack_cd = max(0, self.attack_cd - dt*lira_cooldown_rate*passive_attack_rate)
        self.dash_cd = max(0, self.dash_cd - dt*lira_cooldown_rate)
        self.passive_dash_buff_timer=max(0.0,self.passive_dash_buff_timer-dt)
        self.parry_cd = max(0, self.parry_cd - dt*lira_cooldown_rate)
        self.parry_time = max(0, self.parry_time - dt)
        self.invuln = max(0, self.invuln - dt)
        self.speed_buff = max(0, self.speed_buff - dt)
        self.predator_timer = max(0, self.predator_timer - dt)
        self.hybrid_inertia_timer = max(0.0, self.hybrid_inertia_timer-dt)
        self.ana_forge_cd = max(0.0, getattr(self, "ana_forge_cd", 0.0)-dt)
        self.vasco_immune_text_cd = max(0.0, getattr(self, "vasco_immune_text_cd", 0.0)-dt)
        if self.character == "Vasco" and self.vasco_jackpot_timer > 0:
            before = self.vasco_jackpot_timer
            self.vasco_jackpot_timer = max(0.0, self.vasco_jackpot_timer-dt)
            cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
            self.stamina = cap
            self.vasco_particle_cd -= dt
            if self.vasco_particle_cd <= 0:
                game.spawn_particles(self.pos, VASCO_NEON, 4)
                self.vasco_particle_cd = 0.055
            if before > 0 and self.vasco_jackpot_timer <= 0:
                # Apos o Jackpot, a aposta volta ao meio para impedir loops infinitos de 100%.
                self.vasco_bet_level = 50.0
                game.damage_texts.append(DamageText("JACKPOT ENCERRADO", pygame.Vector2(self.pos), VASCO_GREEN, 0.9))
        if self.character == LIRA_KEY and not game.domain_active and self.lira_domain_buffs:
            self.lira_end_domain(game)
        if self.character == HANK_KEY:
            self.hank_artillery_cd = max(0.0, self.hank_artillery_cd - dt)
            self.hank_charge_time = min(self.hank_charge_required, self.still_timer) if self.still_timer > 0 else 0.0
            if game.domain_active and self.hank_cannon_planted and game.hank_cannon_pos is not None and self.hank_artillery_cd<=0:
                targets=[e for e in game.enemies if not e.dead and game.is_in_domain(e.pos)]
                if targets:
                    origin=pygame.Vector2(game.hank_cannon_pos); target=min(targets,key=lambda e:e.pos.distance_to(origin)); d=target.pos-origin
                    if d.length_squared()>0:
                        d=d.normalize(); shell_r=max(S(18),int(self.radius*0.80))
                        spawn_pos=origin+d*(shell_r+S(28))
                        pr=Projectile(spawn_pos,d*S(690),self.base_damage*1.15*self.projectile_bonus,"player",shell_r,(210,210,210),3.2,0)
                        pr.kind="hank_shell"; pr.origin=pygame.Vector2(origin); pr.hank_domain_cannon=True; pr.hank_explosion_radius=S(155)*(1.25 if self.hank_high_caliber else 1.0); pr.hank_explosion_damage=self.base_damage*1.00*self.projectile_bonus
                        pr.domain_charge_raw=0.0; pr.domain_charge_uses_left=0
                        range_end=hank_range_endpoint(spawn_pos,d); pr.hank_range_origin=pygame.Vector2(spawn_pos); pr.hank_max_distance=max(S(40),spawn_pos.distance_to(range_end))
                        game.projectiles.append(pr); AUDIO.play("hank_cannon",0.90,100); game.shake=max(game.shake,S(8))
                    self.hank_artillery_cd=1.20 if self.hank_madness_combat else 2.0
            if getattr(game, "domain_held", False):
                self.hank_domain_hold += dt
                if self.hank_domain_hold >= 3.0 and not self.hank_domain_triggered:
                    self.hank_domain_triggered = True
                    self.expand_domain(game)
            elif not self.hank_domain_triggered:
                self.hank_domain_hold = 0.0
            if not game.domain_active:
                self.hank_cannon_planted = False
        if self.character == SUKUNA_KEY:
            self.sukuna_slash_fx = max(0.0, self.sukuna_slash_fx-dt)
            if getattr(game, "domain_held", False):
                self.sukuna_domain_hold += dt
                if self.sukuna_domain_hold >= 3.0 and not self.sukuna_domain_triggered:
                    self.sukuna_domain_triggered = True
                    self.activate_sukuna_domain(game)
            elif not self.sukuna_domain_triggered:
                self.sukuna_domain_hold = 0.0
        if self.character == RIP_INDRA_KEY:
            self.rip_click_fx = max(0.0, self.rip_click_fx-dt)

        # Armas Divinas usam gesto de segurar sem disparar o toque curto imediatamente.
        if self.has_divine_attack_hold() and getattr(game,"attack_held",False):
            self.divine_attack_hold += dt
            if self.divine_ana and self.divine_attack_hold>=self.longinus_next_threshold:
                # Primeira orbital exige 2s. Depois, cada nova Ana exige MAIS 3s segurando.
                self.divine_attack_triggered=True
                game.orbital_anas.append(OrbitalAna(self))
                self.longinus_next_threshold += 3.0
                game.damage_texts.append(DamageText("LONGINUS +1",pygame.Vector2(self.pos),DIVINE_BLUE,0.45))
        if self.divine_kevyn and getattr(game,"parry_held",False):
            self.divine_parry_hold+=dt
            if self.divine_parry_hold>=1.0 and not self.divine_parry_triggered:
                self.divine_parry_triggered=True; self.divine_repel(game)
        if self.divine_kevyn and getattr(game,"domain_held",False):
            self.divine_domain_hold+=dt
            if self.divine_domain_hold>=3.0 and not self.divine_domain_triggered:
                if self.divine_purple_burst(game): self.divine_domain_triggered=True
        if (self.divine_ruan or self.divine_kayk or self.divine_pedro or self.divine_kevyn) and getattr(game,"dash_held",False):
            self.divine_dash_hold+=dt
            if self.divine_dash_hold>=1.0 and not self.divine_dash_triggered:
                if self.divine_kevyn:
                    self.divine_pull(game)
                    self.divine_dash_triggered=True
                elif self.divine_ruan:
                    if self.divine_ruan_teleport(game,game.get_move_dir()): self.divine_dash_triggered=True
                elif self.divine_kayk:
                    if self.divine_kayk_reset(game): self.divine_dash_triggered=True
                    else:
                        # Ja foi usado nesta onda: marca como processado para nao disparar Dash ao soltar.
                        self.divine_dash_triggered=True
                        game.damage_texts.append(DamageText("BIG BUILDER: USADO NESTA ONDA",pygame.Vector2(self.pos),GRAY,0.8))
                elif self.divine_pedro:
                    self.plant_divine_pineapple(game)
                    self.divine_dash_triggered=True
        if self.character == "Sans":
            self.sans_blaster_cd=max(0.0,self.sans_blaster_cd-dt)
            self.sans_melee_fx=max(0.0,self.sans_melee_fx-dt)
            self.is_moving = move_dir.length_squared() > 0.01
            if self.stamina <= 0.001:
                self.stamina = 0.0
                self.sans_exhausted = True
        if self.character == "Glonk 100% Power":
            self.glonk_power_fx=max(0.0,self.glonk_power_fx-dt)
        if self.character == "Potential Man":
            self.potential_dog_cd=max(0.0,self.potential_dog_cd-dt)
            self.potential_frog_fx=max(0.0,self.potential_frog_fx-dt)
            if getattr(game, "attack_held", False):
                self.potential_hold_timer += dt
                if self.potential_hold_timer >= 3.0 and not self.potential_hold_triggered:
                    self.potential_hold_triggered = True
                    self.summon_divine_dogs(game)

        if self.character == "Glonk":
            # O destino inevitavel de Glonk: ~2.2 segundos, independente de upgrades permanentes.
            self.hp -= self.max_hp * 0.48 * getattr(self, "glonk_decay_mult", 1.0) * dt
            self.stamina = 0
            if self.hp <= 0:
                self.hp = 0
                game.end_run()
            return

        if move_dir.length_squared() > 0:
            self.still_timer = 0
        else:
            self.still_timer += dt

        speed_mult = 1.35 if self.speed_buff > 0 else 1.0
        if self.character == "Vasco" and self.vasco_high_stakes and self.vasco_bet_level < 30:
            speed_mult *= 1.20
        if self.overclock and self.stamina >= self.max_stamina * 0.80:
            speed_mult *= 1.20
        if self.no_brakes:
            speed_mult *= 1.40
        if self.god_not_watching and self.hp <= self.max_hp * 0.20:
            speed_mult *= 1.55
        if self.character == "Kevyn" and self.in_domain(game):
            speed_mult *= 2.0
        if self.character == "Vasco" and self.vasco_jackpot_timer > 0:
            speed_mult *= 1.80
        if self.character == HANK_KEY and game.domain_active:
            speed_mult *= 2.0
        if getattr(game,"sin_sloth_slow",False):
            speed_mult *= 0.58
        # Sem Estamina Sans ainda consegue se arrastar, mas fica muito mais lento.
        if self.character == "Sans" and self.sans_exhausted:
            speed_mult *= 0.35
        # Anti-teleporte: buffs continuam existindo, mas o multiplicador de caminhada tem teto.
        self.speed_mult = min(speed_mult, 1.85)

        self.stamina_regen_delay = max(0, self.stamina_regen_delay - dt)
        regen = self.stamina_regen
        if self.last_breath and self.hp <= self.max_hp * 0.25:
            regen *= 2.0
        if hasattr(game, "player_in_boss_domain") and game.player_in_boss_domain("void"):
            regen *= 0.22
        # BAD TIME e um modo de risco: recuperacao passiva de Estamina cai para 12%.
        if self.character == "Sans" and getattr(game, "bad_time_active", False):
            regen *= 0.12
        if self.character == HANK_KEY and game.domain_active:
            regen *= 2.4
        if self.stamina_regen_delay <= 0 and self.dash_time <= 0 and self.ruan_attack_time <= 0:
            cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
            self.stamina = min(cap, self.stamina + regen * dt)
        if self.character == "Sans" and self.sans_exhausted:
            # Abaixo de 15% ele continua EXAUSTO: anda devagar, mas ataque/Dash/Blaster ficam bloqueados.
            if self.stamina >= self.max_stamina*0.15:
                self.sans_exhausted=False
                game.damage_texts.append(DamageText("RECUPERADO",pygame.Vector2(self.pos),CYAN,0.8))

        # Kevyn regenera passivamente HP, EXCETO no modo EXTINCAO (cura zero absoluta).
        if self.character == "Kevyn" and self.hp > 0 and getattr(game,"game_mode","normal") != "extinction":
            self.hp = min(self.max_hp, self.hp + 2.0 * dt)

        # Ruan se regenera no Dominio; no EXTINCAO somente Estamina pode voltar, nunca HP.
        if self.character == "Ruan" and self.in_domain(game):
            hp_rate = 0.055 if self.ruan_king_dead else 0.032
            sta_rate = 0.22 if self.ruan_king_dead else 0.13
            if getattr(game,"game_mode","normal") != "extinction":
                self.hp = min(self.max_hp, self.hp + self.max_hp * hp_rate * dt)
            cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
            self.stamina = min(cap, self.stamina + self.max_stamina * sta_rate * dt)

        if getattr(game,"attack_held",False):
            if self.character==RIP_INDRA_KEY: self.rip_hold_time=min(self.rip_charge_max,self.rip_hold_time+dt)
            elif self.character==HISOKA_KEY: self.hisoka_hold_time=min(self.hisoka_charge_max,self.hisoka_hold_time+dt)

        # Ataque do Ruan: dash ofensivo separado do botao DASH comum.
        if self.character == "Ruan" and self.ruan_attack_time > 0:
            self.ruan_attack_time -= dt
            dash_mult = 5.2 if self.ruan_necro_step else 4.35
            dash_base = min(self.base_speed, S(560))
            self.pos += self.ruan_attack_dir * dash_base * dash_mult * dt
            hit_any = False
            for e in list(game.enemies):
                if e.dead or e.id in self.ruan_hit_ids:
                    continue
                if e.pos.distance_to(self.pos) <= self.radius + e.radius + S(20):
                    self.ruan_hit_ids.add(e.id)
                    old = game.current_damage_kind
                    game.current_damage_kind = "ruan_dash"
                    dmg = self.base_damage * self.effective_damage_mult(game, e, "ruan_dash", e.pos.distance_to(self.pos))
                    e.damage(dmg, game, self.pos)
                    game.current_damage_kind = old
                    self.recover_stamina(self.stamina_on_hit, game)
                    hit_any = True
            maho=getattr(game,"mahoraga",None)
            if maho is not None and not maho.dead and maho.pos.distance_to(self.pos) <= self.radius+maho.radius+S(20):
                if "mahoraga" not in self.ruan_hit_ids:
                    self.ruan_hit_ids.add("mahoraga")
                    dmg=self.base_damage*self.effective_damage_mult(game,None,"ruan_dash",maho.pos.distance_to(self.pos))
                    maho.take_damage(dmg,game,self.pos,from_player=True)
                    hit_any=True
            if hit_any:
                game.register_combo_hit()
                if not self.ruan_domain_charge_awarded:
                    game.domain_charge_primary_hit(20.0)
                    self.ruan_domain_charge_awarded = True
            if self.forge_ruan and random.random() < 0.55:
                game.forge_fire_trails.append(ForgeFireTrail(self.pos, max(2.0, self.base_damage*0.22)))
            game.spawn_particles(self.pos, CYAN, 1)
        elif self.dash_time > 0:
            self.dash_time -= dt
            dash_base = min(self.base_speed, S(560))
            if self.character==LIRA_KEY and game.domain_active and "speed" in self.lira_domain_buffs: dash_base*=1.50
            self.pos += self.dash_dir * dash_base * (3.7 if (self.ana_vector_step or (self.character == "Kayk" and self.kayk_spectral_step)) else 3.2) * dt
            if self.forge_ruan and random.random() < 0.55:
                game.forge_fire_trails.append(ForgeFireTrail(self.pos, max(2.0, self.base_damage*0.18)))
            game.spawn_particles(self.pos, CYAN, 1)
        elif move_dir.length_squared() > 0:
            d = move_dir.normalize()
            self.facing = d
            walk_speed = min(self.base_speed * self.speed_mult, S(700))
            if self.character==LIRA_KEY and game.domain_active and "speed" in self.lira_domain_buffs: walk_speed*=1.50
            self.pos += d * walk_speed * dt

        self.pos.x = clamp(self.pos.x, self.radius, W - self.radius)
        self.pos.y = clamp(self.pos.y, S(205) + self.radius, H - S(335) - self.radius)

    def draw(self, offset, game):
        p = self.pos + offset
        color = self.color if self.invuln <= 0 else WHITE
        pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius)
        if self.character == LIRA_KEY:
            # Lira: corpo vermelho com contorno dourado.
            pygame.draw.circle(SCREEN, LIRA_ACCENT, (int(p.x), int(p.y)), self.radius, max(2,S(5)))
            # Visual da C#nsur#: precisa ser desenhado aqui, onde `p` existe.
            band=pygame.Rect(int(p.x-self.radius*0.75),int(p.y-self.radius*0.18),int(self.radius*1.5),max(S(8),int(self.radius*0.36)))
            pygame.draw.rect(SCREEN,DARK,band,border_radius=max(1,S(3)))
            pygame.draw.rect(SCREEN,LIRA_ACCENT,band,max(1,S(2)),border_radius=max(1,S(3)))
        if self.character == "Vasco" and self.vasco_jackpot_timer > 0:
            pygame.draw.circle(SCREEN, VASCO_NEON, (int(p.x), int(p.y)), self.radius+S(8), max(2,S(4)))
        if self.character == "Vasco" and self.divine_vasco:
            wheel = pygame.Vector2(p.x, p.y-self.radius-S(28))
            wr = S(15)
            pygame.draw.circle(SCREEN, DIVINE_BLUE, (int(wheel.x),int(wheel.y)), wr, max(1,S(3)))
            for i in range(8):
                d=vec_from_angle(i*math.tau/8)
                a=wheel+d*S(4); b=wheel+d*wr
                pygame.draw.line(SCREEN,DIVINE_BLUE,(int(a.x),int(a.y)),(int(b.x),int(b.y)),max(1,S(2)))
            if self.vasco_dharma_reduction > 0:
                draw_text(f"-{int(self.vasco_dharma_reduction*100)}%", FONT_S, DIVINE_BLUE, (wheel.x, wheel.y-S(25)), True)
        if self.character == "Potential Man":
            pygame.draw.circle(SCREEN, WHITE, (int(p.x), int(p.y)), self.radius, max(2,S(5)))
        if self.character == SUKUNA_KEY:
            # Corpo branco + cabelo rosa em espinhos inspirado no visual do Itadori.
            r=self.radius
            pygame.draw.circle(SCREEN,SUKUNA_HAIR,(int(p.x),int(p.y-r*0.10)),int(r*0.96))
            hair=[(p.x-r*0.98,p.y-r*0.08),(p.x-r*0.86,p.y-r*0.62),(p.x-r*0.62,p.y-r*1.08),(p.x-r*0.28,p.y-r*0.76),
                  (p.x,p.y-r*1.20),(p.x+r*0.28,p.y-r*0.76),(p.x+r*0.62,p.y-r*1.08),(p.x+r*0.86,p.y-r*0.62),
                  (p.x+r*0.98,p.y-r*0.08),(p.x+r*0.72,p.y-r*0.26),(p.x-r*0.72,p.y-r*0.26)]
            pygame.draw.polygon(SCREEN,SUKUNA_HAIR,[(int(x),int(y)) for x,y in hair])
            pygame.draw.circle(SCREEN,SUKUNA_SLASH,(int(p.x-r*0.28),int(p.y+S(2))),max(2,S(3)))
            pygame.draw.circle(SCREEN,SUKUNA_SLASH,(int(p.x+r*0.28),int(p.y+S(2))),max(2,S(3)))
        if self.character == RIP_INDRA_KEY:
            # Tres laminas curtas nas costas deixam o Pac-Man reconhecivel sem sprites pesados.
            for off in (-1,0,1):
                x=p.x+off*S(10); pygame.draw.line(SCREEN,DARK,(int(x),int(p.y-S(8))),(int(x+off*S(6)),int(p.y-self.radius-S(24))),max(2,S(3)))
            if self.rip_click_fx > 0:
                d=self.rip_click_dir if self.rip_click_dir.length_squared() else pygame.Vector2(1,0)
                d=d.normalize(); side=pygame.Vector2(-d.y,d.x)
                reach=S(210)*self.rip_range_mult
                near=p+d*S(28)
                far=p+d*reach
                width=S(36)+S(30)*(self.rip_click_fx/0.16)
                pts=[near+side*width*0.50, far+side*width, far-side*width, near-side*width*0.50]
                pygame.draw.polygon(SCREEN, RIP_INDRA_COLOR, [(int(v.x),int(v.y)) for v in pts])
                pygame.draw.polygon(SCREEN, WHITE, [(int(v.x),int(v.y)) for v in pts], max(1,S(3)))
                for off in (-0.20,0.0,0.20):
                    sd=vec_from_angle(math.atan2(d.y,d.x)+off)
                    a=p+sd*S(46); b=p+sd*(reach*0.98)
                    pygame.draw.line(SCREEN, WHITE, (int(a.x),int(a.y)), (int(b.x),int(b.y)), max(1,S(2)))
        if self.character == HISOKA_KEY:
            pygame.draw.circle(SCREEN,WHITE,(int(p.x-S(9)),int(p.y-S(5))),max(2,S(3)))
            pygame.draw.circle(SCREEN,WHITE,(int(p.x+S(9)),int(p.y-S(5))),max(2,S(3)))
            pygame.draw.polygon(SCREEN,YELLOW,[(int(p.x),int(p.y+S(3))),(int(p.x-S(5)),int(p.y+S(11))),(int(p.x+S(5)),int(p.y+S(11)))])
        if self.character == HANK_KEY:
            # Dois pontos vermelhos simples e baratos: os oculos do Hank.
            ey=p.y-S(4); ex=S(9); rr=max(2,S(5))
            pygame.draw.line(SCREEN,(175,20,30),(int(p.x-ex+rr),int(ey)),(int(p.x+ex-rr),int(ey)),max(1,S(2)))
            pygame.draw.circle(SCREEN,(230,35,45),(int(p.x-ex),int(ey)),rr)
            pygame.draw.circle(SCREEN,(230,35,45),(int(p.x+ex),int(ey)),rr)
            pygame.draw.circle(SCREEN,DARK,(int(p.x-ex),int(ey)),rr,max(1,S(1)))
            pygame.draw.circle(SCREEN,DARK,(int(p.x+ex),int(ey)),rr,max(1,S(1)))
        pygame.draw.line(SCREEN, DARK, (int(p.x), int(p.y)), (int(p.x + self.facing.x * S(36)), int(p.y + self.facing.y * S(36))), S(7))
        if self.character == "Potential Man":
            if self.potential_frog_fx > 0:
                d=self.potential_frog_dir if self.potential_frog_dir.length_squared() else pygame.Vector2(1,0)
                d=d.normalize(); side=pygame.Vector2(-d.y,d.x)
                tip=p+d*S(235); near=p+d*S(20)
                pts=[near+side*S(22), tip+side*S(105), tip-side*S(105), near-side*S(22)]
                pygame.draw.polygon(SCREEN, PINK, [(int(x.x),int(x.y)) for x in pts])
                pygame.draw.polygon(SCREEN, WHITE, [(int(x.x),int(x.y)) for x in pts], max(1,S(3)))
            if getattr(game, "attack_held", False) and not self.potential_hold_triggered:
                bw=S(120); bh=S(10); ratio=clamp(self.potential_hold_timer/3.0,0,1)
                bx=p.x-bw/2; by=p.y-self.radius-S(34)
                pygame.draw.rect(SCREEN,DARK,(bx,by,bw,bh),border_radius=max(1,S(4)))
                pygame.draw.rect(SCREEN,WHITE,(bx,by,bw*ratio,bh),border_radius=max(1,S(4)))
        if self.divine_kevyn and getattr(game,"domain_held",False):
            ratio=clamp(self.divine_domain_hold/3.0,0,1)
            pygame.draw.circle(SCREEN,PURPLE,(int(p.x),int(p.y)),int(self.radius+S(16)+S(28)*ratio),max(2,S(5)))
        if self.character == HANK_KEY:
            bw=S(120); bh=S(10); bx=p.x-bw/2; by=p.y-self.radius-S(34)
            ratio=clamp(self.hank_charge_time/max(0.01,self.hank_charge_required),0,1)
            pygame.draw.rect(SCREEN,DARK,(bx,by,bw,bh),border_radius=max(1,S(4)))
            pygame.draw.rect(SCREEN,GREEN if ratio>=0.999 else YELLOW,(bx,by,bw*ratio,bh),border_radius=max(1,S(4)))
            if getattr(game,"domain_held",False):
                hr=clamp(self.hank_domain_hold/3.0,0,1)
                pygame.draw.circle(SCREEN,RED,(int(p.x),int(p.y)),int(self.radius+S(16)+S(24)*hr),max(2,S(4)))
            if self.hank_cannon_planted and game.domain_active:
                draw_text("FACAS", FONT_S, WHITE, (p.x, p.y+self.radius+S(18)), True)
        if self.character == SUKUNA_KEY and getattr(game,"domain_held",False):
            sr=clamp(self.sukuna_domain_hold/3.0,0,1)
            pygame.draw.circle(SCREEN,SUKUNA_SLASH,(int(p.x),int(p.y)),int(self.radius+S(14)+S(28)*sr),max(2,S(4)))
        if self.character in (RIP_INDRA_KEY,HISOKA_KEY) and getattr(game,"attack_held",False):
            held=self.rip_hold_time if self.character==RIP_INDRA_KEY else self.hisoka_hold_time
            maxh=self.rip_charge_max if self.character==RIP_INDRA_KEY else self.hisoka_charge_max
            bw=S(120); bh=S(9); bx=p.x-bw/2; by=p.y-self.radius-S(34); rr=clamp(held/maxh,0,1)
            pygame.draw.rect(SCREEN,DARK,(bx,by,bw,bh),border_radius=max(1,S(4)))
            pygame.draw.rect(SCREEN,RIP_INDRA_COLOR if self.character==RIP_INDRA_KEY else HISOKA_COLOR,(bx,by,bw*rr,bh),border_radius=max(1,S(4)))
        if self.shield > 0:
            pygame.draw.circle(SCREEN, BLUE, (int(p.x), int(p.y)), self.radius + S(10), S(4))
        if self.parry_time > 0 and self.character != "Sans":
            pygame.draw.circle(SCREEN, YELLOW, (int(p.x), int(p.y)), S(80), S(8))
        if self.character == "Sans":
            if self.sans_melee_fx > 0:
                d = self.sans_melee_dir if self.sans_melee_dir.length_squared() > 0 else self.facing
                bone_center = p + d.normalize()*S(76)
                draw_bone_rect(bone_center, d, S(120), S(20), WHITE)
            if self.sans_exhausted:
                draw_text("EXAUSTO",FONT_S,RED,(p.x,p.y-self.radius-S(38)),True)
        if self.character == "Glonk 100% Power" and self.glonk_power_fx > 0:
            d = self.glonk_power_dir if self.glonk_power_dir.length_squared() > 0 else pygame.Vector2(1,0)
            end = p + d.normalize()*S(300)
            pygame.draw.line(SCREEN, GREEN, p, end, max(S(18),S(26)))
            pygame.draw.circle(SCREEN, WHITE, (int(end.x),int(end.y)), S(16), max(1,S(3)))
        if self.character == SUKUNA_KEY and self.sukuna_slash_fx > 0:
            d=self.facing.normalize() if self.facing.length_squared() else pygame.Vector2(1,0)
            n=pygame.Vector2(-d.y,d.x); center=p+d*S(48)
            pygame.draw.line(SCREEN,(255,235,225),center-n*S(52),center+n*S(52),max(2,S(8)))
            pygame.draw.line(SCREEN,SUKUNA_COLOR,center-n*S(48),center+n*S(48),max(1,S(3)))
        if game.slash_fx > 0 and (self.weapon == 0 or self.character == HANK_KEY):
            a = math.atan2(self.facing.y, self.facing.x)
            r = S(105) * self.kevyn_sword_range
            rect = pygame.Rect(p.x-r, p.y-r, r*2, r*2)
            pygame.draw.arc(SCREEN, WHITE, rect, -(a+0.8), -(a-0.8), S(9))



class RivalMiniAna:
    def __init__(self, pos, damage, color=PINK):
        self.pos=pygame.Vector2(pos); self.damage=damage; self.color=color; self.radius=S(15); self.speed=S(185); self.dead=False; self.life=5.0
    def update(self,dt,game):
        if self.dead:return False
        self.life-=dt
        d=game.player.pos-self.pos; dist=d.length()
        if dist>0:self.pos += d.normalize()*self.speed*dt
        if dist <= self.radius+game.player.radius+S(7):
            game.player.take_damage(self.damage,game); game.spawn_particles(self.pos,PINK,8); self.dead=True
        return (not self.dead) and self.life>0
    def draw(self,offset):
        p=self.pos+offset; pygame.draw.circle(SCREEN,PINK,(int(p.x),int(p.y)),self.radius); pygame.draw.circle(SCREEN,WHITE,(int(p.x),int(p.y)),self.radius,max(1,S(2)))
        draw_text("ANA",FONT_S,DARK,(p.x,p.y),True)

class RivalMinion:
    def __init__(self,pos,kind,damage,color=CYAN,big=False):
        self.pos=pygame.Vector2(pos); self.kind=kind; self.damage=damage; self.color=color; self.radius=S(55 if big else 23); self.speed=S(145 if big else 190); self.dead=False; self.cd=0.0; self.life=9.0 if big else 6.0
    def update(self,dt,game):
        if self.dead:return False
        self.life-=dt; self.cd=max(0.0,self.cd-dt)
        d=game.player.pos-self.pos; dist=max(1.0,d.length()); n=d/dist
        if self.kind=="turret":
            if self.cd<=0:
                game.projectiles.append(Projectile(self.pos,n*S(440),max(7,self.damage*0.72),"enemy",S(8),RED,2.5)); self.cd=0.65
        else:
            if dist>self.radius+game.player.radius+S(10): self.pos += n*self.speed*dt
            elif self.cd<=0:
                game.player.take_damage(self.damage,game); self.cd=0.65 if self.kind!="mahoraga" else 0.45
        return self.life>0 and not self.dead
    def draw(self,offset):
        p=self.pos+offset; pygame.draw.circle(SCREEN,self.color,(int(p.x),int(p.y)),self.radius); pygame.draw.circle(SCREEN,WHITE,(int(p.x),int(p.y)),self.radius,max(1,S(3)))
        draw_text({"dog":"CAO","friend":"AMIGO","guardian":"GUARDIAO","mahoraga":"MAHORAGA","turret":"TORRE"}.get(self.kind,self.kind.upper()),FONT_S,DARK if self.kind!="mahoraga" else WHITE,(p.x,p.y),True)

class RivalBoomerang:
    def __init__(self,owner,direction,damage,size_mult=1.0,range_mult=1.0):
        d=pygame.Vector2(direction); d=d.normalize() if d.length_squared() else pygame.Vector2(1,0)
        self.owner=owner; self.pos=pygame.Vector2(owner.pos)+d*S(42); self.vel=d*S(540); self.damage=damage; self.radius=max(S(15),int(S(15)*size_mult)); self.timer=0.48*range_mult; self.returning=False; self.dead=False; self.hit_out=False; self.hit_back=False
    def update(self,dt,game):
        self.timer-=dt
        if not self.returning and self.timer<=0:self.returning=True
        if self.returning:
            d=self.owner.pos-self.pos; dist=d.length()
            if dist<S(38):return False
            if dist>0:self.vel=self.vel.lerp(d.normalize()*S(565),min(1.0,dt*9))
        self.pos += self.vel*dt
        dist=self.pos.distance_to(game.player.pos)
        already=self.hit_back if self.returning else self.hit_out
        if not already and dist<=self.radius+game.player.radius:
            game.player.take_damage(self.damage,game)
            if self.returning:self.hit_back=True
            else:self.hit_out=True
        return -S(120)<self.pos.x<W+S(120) and -S(120)<self.pos.y<H+S(120)
    def draw(self,offset):
        p=self.pos+offset; pygame.draw.circle(SCREEN,YELLOW,(int(p.x),int(p.y)),self.radius); pygame.draw.circle(SCREEN,GREEN,(int(p.x),int(p.y-self.radius)),max(2,S(5)))

class RivalGuardianEnemy(Enemy):
    """Guardiao hostil do Ruan em UM CONTRA TODOS. Entra em game.enemies para possuir hitbox real."""
    def __init__(self,pos,wave,damage,owner_rival=None):
        super().__init__(pos,"tank",max(1,wave),None)
        self.kind="rival_guardian"; self.owner_rival=owner_rival; self.color=CYAN; self.radius=S(55)
        self.max_hp=max(120.0,self.max_hp*0.72); self.hp=self.max_hp; self.speed=S(175); self.contact_damage=max(9.0,damage)
        self.coin_value=0; self.life=10.0
    def update(self,dt,game):
        if self.dead:return
        self.life-=dt
        if self.life<=0:
            self.dead=True; return
        self.flash=max(0.0,self.flash-dt); self.touch_cd=max(0.0,self.touch_cd-dt)
        d=game.player.pos-self.pos; dist=max(1.0,d.length()); n=d/dist
        if dist>self.radius+game.player.radius+S(8): self.pos += n*self.speed*dt
        elif self.touch_cd<=0:
            game.player.take_damage(self.contact_damage,game); self.touch_cd=0.55
        self.pos.x=clamp(self.pos.x,self.radius,W-self.radius); self.pos.y=clamp(self.pos.y,S(180)+self.radius,H-S(335)-self.radius)
    def die(self,game):
        if self.dead:return
        self.dead=True; game.spawn_particles(self.pos,CYAN,10)
    def draw(self,offset):
        p=self.pos+offset; col=WHITE if self.flash>0 else CYAN
        pygame.draw.circle(SCREEN,col,(int(p.x),int(p.y)),self.radius); pygame.draw.circle(SCREEN,WHITE,(int(p.x),int(p.y)),self.radius,max(2,S(3)))
        draw_text("GUARDIAO",FONT_S,DARK,(p.x,p.y),True)
        bw=self.radius*2; y=p.y-self.radius-S(14); pygame.draw.rect(SCREEN,DARK,(p.x-bw/2,y,bw,S(6))); pygame.draw.rect(SCREEN,GREEN,(p.x-bw/2,y,bw*clamp(self.hp/max(1,self.max_hp),0,1),S(6)))

class CharacterRival(Boss):
    """UM CONTRA TODOS: cada rival usa o kit real/adaptado do proprio personagem, nao um Boss generico."""
    def __init__(self,pos,wave,character_name):
        super().__init__(pos,max(5,wave*5))
        self.rival_character=character_name; cfg=CHARACTER_CONFIG.get(character_name,CHARACTER_CONFIG["Ycaro"])
        self.variant="rival"; self.name=character_name.upper(); self.color=cfg["color"]; self.domain_name=cfg.get("domain","NENHUM")
        self.max_hp*=0.82+0.09*wave; self.hp=self.max_hp; self.contact_damage*=0.72+0.035*wave
        self.speed=min(S(230),max(S(105),cfg.get("speed",280)*0.48)); self.radius=S(56)
        self.rival_attack_cd=0.35; self.rival_special_cd=4.2; self.rival_buff_timer=0.0; self.rival_dash_time=0.0; self.rival_dash_dir=pygame.Vector2(1,0)
        self.rival_mobility_cd=random.uniform(1.8,2.8); self.rival_parry_cd=random.uniform(2.8,4.2); self.rival_parry_time=0.0
        self.rival_minions=[]; self.rival_boomerangs=[]; self.facing=pygame.Vector2(-1,0); self.rival_fx=0.0
        # Vasco rival: replica a aposta e o Jackpot para o modo UM CONTRA TODOS.
        self.rival_vasco_bet=50.0
        self.rival_vasco_jackpot=0.0
        self.rival_vasco_particle_cd=0.0
        # Boss-rival nao usa rajadas genericas, mas agora pode usar o Dominio do proprio personagem.
        self.domain_active=False; self.domain_timer=0.0; self.domain_tick=0.0
        self.domain_center=pygame.Vector2(self.pos); self.domain_radius=S(450)
        can_domain = self.domain_name not in ("NENHUM", "MAHORAGA") and character_name not in ("Potential Man", "Glonk", "Glonk 100% Power", "Vinicius 13")
        self.domain_cd=random.uniform(5.5,8.0) if can_domain else 99999.0
        self.burst_cd=99999; self.charge_cd=99999

    def damage(self,amount,game,source_pos=None,minimal_fx=False):
        # Vasco rival tambem fica realmente imortal durante os 8s do Jackpot.
        if self.rival_character=="Vasco" and self.rival_vasco_jackpot>0:
            if not minimal_fx:
                game.damage_texts.append(DamageText("JACKPOT - IMORTAL",pygame.Vector2(self.pos),VASCO_NEON,0.45))
            return
        # Kevyn rival pode realmente dar Parry por uma janela curta.
        if self.rival_character=="Kevyn" and self.rival_parry_time>0:
            if not minimal_fx:
                game.damage_texts.append(DamageText("PARRY!",pygame.Vector2(self.pos),YELLOW,0.55))
                game.spawn_particles(self.pos,YELLOW,5)
            return
        super().damage(amount,game,source_pos,minimal_fx)

    def _proj(self,game,d,damage,speed=S(430),radius=S(9),color=None,life=2.6):
        d=pygame.Vector2(d); d=d.normalize() if d.length_squared() else pygame.Vector2(1,0)
        game.projectiles.append(Projectile(self.pos+d*S(40),d*speed,damage,"enemy",radius,color or self.color,life))

    def _move(self,dt,game,d,dist):
        c=self.rival_character
        # Glonk normal e fiel ao personagem: nao luta nem anda como Boss.
        if c == "Glonk":
            return
        # Kits melee fecham distancia; atiradores tentam manter espaco.
        if c in ("Kevyn","Ruan","Colosso do Caos","Glonk 100% Power"):
            if dist>S(150): self.pos += d*self.speed*dt
        elif c=="Sans":
            if dist<S(190): self.pos -= d*self.speed*0.65*dt
            elif dist>S(360): self.pos += d*self.speed*0.55*dt
        elif c=="Potential Man":
            if dist<S(180): self.pos -= d*self.speed*0.55*dt
            elif dist>S(330): self.pos += d*self.speed*0.45*dt
        else:
            if dist<S(220): self.pos -= d*self.speed*0.55*dt
            elif dist>S(430): self.pos += d*self.speed*0.42*dt

    def _basic_attack(self,game,d,dist):
        c=self.rival_character; dmg=max(10.0,game.player.max_hp*0.060)
        if c=="Glonk":
            # O Glonk jogavel literalmente nao faz nada.
            self.rival_attack_cd=2.0
        elif c=="Ana":
            count=random.randint(1,3)
            for i in range(count):
                ang=i*math.tau/max(1,count); self.rival_minions.append(RivalMiniAna(self.pos+vec_from_angle(ang)*S(44),dmg*0.82))
            self.rival_attack_cd=1.35
        elif c=="Kevyn":
            if dist<=S(150): game.player.take_damage(dmg*1.35,game); self.rival_fx=0.18
            self.rival_attack_cd=0.48
        elif c=="Ycaro":
            a=math.atan2(d.y,d.x)
            for off in (-0.22,-0.11,0,0.11,0.22): self._proj(game,vec_from_angle(a+off),dmg*0.58,S(500),S(7),ORANGE,1.2)
            self.rival_attack_cd=0.72
        elif c=="Kayk":
            a=math.atan2(d.y,d.x)
            for off in (-0.06,0.06): self._proj(game,vec_from_angle(a+off),dmg*0.75,S(560),S(7),PURPLE,2.0)
            self.rival_attack_cd=0.34
        elif c=="Pedro":
            self.rival_boomerangs.append(RivalBoomerang(self,d,dmg*1.05,1.65,1.60)); self.rival_attack_cd=0.86
        elif c=="Vasco":
            forced_positive = self.domain_active
            if forced_positive:
                result="win"
            else:
                result=("lose","neutral","win")[random.randrange(3)]
            if result=="win":
                self.rival_vasco_bet=min(100.0,self.rival_vasco_bet+10.0)
                game.damage_texts.append(DamageText("GANHOU +10",pygame.Vector2(self.pos),VASCO_NEON,0.45))
            elif result=="lose":
                loss=random.randint(10,15)
                self.rival_vasco_bet=max(0.0,self.rival_vasco_bet-loss)
                game.damage_texts.append(DamageText(f"PERDEU -{loss}",pygame.Vector2(self.pos),RED,0.45))
            else:
                game.damage_texts.append(DamageText("NEUTRO",pygame.Vector2(self.pos),GRAY,0.45))
            bet_mult=0.20+1.70*clamp(self.rival_vasco_bet/100.0,0.0,1.0)
            a=math.atan2(d.y,d.x)
            for off in (-0.12,0.0,0.12):
                sd=vec_from_angle(a+off)
                pr=Projectile(self.pos+sd*S(38),sd*S(620),dmg*bet_mult*0.42,"enemy",S(10),VASCO_GREEN,2.5)
                pr.kind="rival_vasco_bet"; pr.rival_vasco_owner=self
                game.projectiles.append(pr)
            self.rival_attack_cd=0.42 if self.rival_vasco_jackpot<=0 else 0.24
            if forced_positive and self.rival_vasco_bet>=100.0 and self.rival_vasco_jackpot<=0:
                self.domain_active=False; self.domain_timer=0.0; self.rival_vasco_jackpot=8.0; self.domain_cd=99999.0
                game.damage_texts.append(DamageText("JACKPOT!",pygame.Vector2(self.pos),VASCO_NEON,1.0))
                game.spawn_particles(self.pos,VASCO_NEON,24); game.shake=max(game.shake,S(10))
        elif c=="Ruan":
            self.rival_dash_time=0.26; self.rival_dash_dir=pygame.Vector2(d); self.rival_attack_cd=0.72
        elif c=="Colosso do Caos":
            radius=S(255); self.rival_fx=0.25
            if dist<=radius+game.player.radius: game.player.take_damage(dmg*1.25,game)
            self.rival_attack_cd=0.95
        elif c=="Sans":
            if dist<S(145): game.player.take_damage(dmg*0.95,game); self.rival_fx=0.16
            else: self._proj(game,d,dmg*0.75,S(650),S(8),WHITE,2.1)
            self.rival_attack_cd=0.52
        elif c=="Strikada Egoísta":
            self._proj(game,d,dmg*1.0,S(520),S(15),(125,220,255),3.0); self.rival_attack_cd=1.25
        elif c=="Glonk 100% Power":
            if dist<=S(175): game.player.take_damage(max(1,dmg*0.65),game); self.rival_fx=0.18
            self.rival_attack_cd=0.48
        elif c=="Potential Man":
            # Sapos: cone rosa na frente.
            if dist<=S(250): game.player.take_damage(dmg*0.9,game)
            self.rival_fx=0.20; self.rival_attack_cd=0.70
        elif c=="Vinicius 13":
            self._proj(game,d,dmg*0.72,S(520),S(8),RED,2.4); self.rival_attack_cd=0.45
        else:
            self._proj(game,d,dmg,S(450),S(9),self.color,2.4); self.rival_attack_cd=0.70

    def _special(self,game,d,dist):
        c=self.rival_character; dmg=max(12.0,game.player.max_hp*0.075)
        if c=="Glonk":
            self.rival_special_cd=6.0
            return
        if c=="Ana":
            # Explosao de Reality: chuva curta de Mini-Anas.
            for i in range(5): self.rival_minions.append(RivalMiniAna(self.pos+vec_from_angle(i*math.tau/5)*S(65),dmg*0.75))
        elif c=="Kevyn":
            # Parry/repulsao: apaga projeteis do jogador proximos e avanca para melee.
            game.projectiles=[p for p in game.projectiles if not (p.owner=="player" and p.pos.distance_to(self.pos)<S(260))]
            self.pos += d*S(90); self.rival_fx=0.22
        elif c=="Ycaro":
            # Campo de Caca: rajada shotgun muito rapida.
            a=math.atan2(d.y,d.x)
            for off in (-0.34,-0.23,-0.12,0,0.12,0.23,0.34): self._proj(game,vec_from_angle(a+off),dmg*0.60,S(620),S(7),ORANGE,1.1)
        elif c=="Kayk":
            # Necropole: almas/tiros em leque.
            a=math.atan2(d.y,d.x)
            for off in (-0.30,-0.15,0,0.15,0.30): self._proj(game,vec_from_angle(a+off),dmg*0.70,S(600),S(8),PURPLE,2.2)
        elif c=="Pedro":
            # X da Colheita: 4 abacaxis diagonais.
            for i in range(4): self.rival_boomerangs.append(RivalBoomerang(self,vec_from_angle(math.pi/4+i*math.pi/2),dmg*0.9,1.55,1.45))
        elif c=="Vasco":
            # O especial do Vasco e mobilidade/aposta, sem criar uma segunda regra de dano.
            side=pygame.Vector2(-d.y,d.x)
            if random.random()<0.5: side*=-1
            self.pos += side*S(120)
            self.rival_special_cd=3.2
        elif c=="Ruan":
            # Guardiao entra na lista real de inimigos para ter hitbox e poder ser morto por QUALQUER ataque do jogador.
            gpos=self.pos+vec_from_angle(random.random()*math.tau)*S(70)
            game.enemies.append(RivalGuardianEnemy(gpos,max(1,getattr(game,"wave",1)),dmg*0.95,self))
        elif c=="Colosso do Caos":
            radius=S(420); self.rival_fx=0.40
            if dist<=radius+game.player.radius: game.player.take_damage(dmg*1.55,game)
        elif c=="Sans":
            # Blaster: linha direta de alto dano.
            if abs((game.player.pos-self.pos).cross(d))<S(85): game.player.take_damage(dmg*1.45,game)
            self.rival_fx=0.32
        elif c=="Strikada Egoísta":
            # Metavisao: bola forte teleguiada ao alvo atual.
            self._proj(game,d,dmg*1.25,S(660),S(18),(125,220,255),3.4)
        elif c=="Glonk 100% Power":
            self.pos += d*S(125)
            if self.pos.distance_to(game.player.pos)<=S(190): game.player.take_damage(max(1,dmg),game)
        elif c=="Potential Man":
            # Caes Divinos; em usos posteriores pode aparecer um Mahoraga temporario.
            self.rival_minions.append(RivalMinion(self.pos+pygame.Vector2(S(45),0),"dog",dmg*0.7,WHITE))
            self.rival_minions.append(RivalMinion(self.pos-pygame.Vector2(S(45),0),"dog",dmg*0.7,WHITE))
            if random.random()<0.35:self.rival_minions.append(RivalMinion(self.pos+pygame.Vector2(0,S(80)),"mahoraga",dmg*1.15,PURPLE,True))
        elif c=="Vinicius 13":
            # Construcao automatica: torreta temporaria.
            self.rival_minions.append(RivalMinion(self.pos+vec_from_angle(random.random()*math.tau)*S(90),"turret",dmg*0.8,RED))
        if c!="Vasco":
            self.rival_special_cd=4.5
        game.damage_texts.append(DamageText(self.name+"!",pygame.Vector2(self.pos),self.color,0.65))

    def _update_rival_domain(self, dt, game):
        if self.domain_active:
            self.domain_timer -= dt
            self.domain_tick -= dt
            if self.domain_timer <= 0:
                self.domain_active=False; self.domain_timer=0.0
                return
            inside=self.is_in_domain(game.player.pos)
            c=self.rival_character
            # O efeito acompanha o kit do personagem em vez de virar um dano generico.
            if c=="Ana" and self.domain_tick<=0:
                to=game.player.pos-self.pos; d=to.normalize() if to.length_squared() else pygame.Vector2(1,0)
                self.rival_minions.append(RivalMiniAna(self.pos+d*S(45),max(10.0,game.player.max_hp*0.055)))
                self.domain_tick=0.60
            elif c=="Kevyn":
                # Dentro do Trono o Kevyn fica muito mais insistente no corpo a corpo.
                self.rival_attack_cd -= dt*1.6
                self.rival_mobility_cd -= dt*0.8
            elif c=="Ycaro" and self.domain_tick<=0:
                to=game.player.pos-self.pos; d=to.normalize() if to.length_squared() else pygame.Vector2(1,0)
                self._proj(game,d,max(9.0,game.player.max_hp*0.045),S(650),S(7),ORANGE,1.3); self.domain_tick=0.34
            elif c=="Kayk" and self.domain_tick<=0:
                to=game.player.pos-self.pos; a=math.atan2(to.y,to.x) if to.length_squared() else 0
                for off in (-0.12,0.12): self._proj(game,vec_from_angle(a+off),max(8.0,game.player.max_hp*0.040),S(620),S(7),PURPLE,2.0)
                self.domain_tick=0.30
            elif c=="Pedro" and self.domain_tick<=0:
                dmg=max(9.0,game.player.max_hp*0.045)
                for i in range(4): self.rival_boomerangs.append(RivalBoomerang(self,vec_from_angle(math.pi/4+i*math.pi/2),dmg,1.45,1.35))
                self.domain_tick=0.95
            elif c=="Vasco":
                # I JUST HIT THE JACKPOT: o efeito real ocorre no ataque — toda aposta vira positiva.
                pass
            elif c=="Ruan" and self.domain_tick<=0:
                # Guarda do Dominio com hitbox real.
                if not any(isinstance(e,RivalGuardianEnemy) and not e.dead and getattr(e,"owner_rival",None) is self for e in game.enemies):
                    game.enemies.append(RivalGuardianEnemy(self.pos+pygame.Vector2(S(70),0),max(1,getattr(game,"wave",1)),max(10.0,game.player.max_hp*0.05),self))
                self.domain_tick=1.3
            elif c=="Colosso do Caos" and inside and self.domain_tick<=0:
                if game.player.character not in ("Glonk", "Glonk 100% Power"):
                    game.player.take_damage(max(10.0,game.player.max_hp*0.07),game)
                self.domain_tick=0.82
            elif c=="Strikada Egoísta" and self.domain_tick<=0:
                to=game.player.pos-self.pos; d=to.normalize() if to.length_squared() else pygame.Vector2(1,0)
                self._proj(game,d,max(10.0,game.player.max_hp*0.05),S(700),S(18),(125,220,255),3.2); self.domain_tick=0.58
            elif c=="Sans" and self.domain_tick<=0:
                for i in range(4): self._proj(game,vec_from_angle(i*math.pi/2),max(8.0,game.player.max_hp*0.04),S(520),S(8),WHITE,2.2)
                self.domain_tick=0.50
        elif self.domain_cd < 99990:
            self.domain_cd -= dt
            if self.domain_cd <= 0:
                self.activate_domain(game)

    def update(self,dt,game):
        if self.dead:return
        self.flash=max(0,self.flash-dt); self.rival_attack_cd-=dt; self.rival_special_cd-=dt; self.rival_buff_timer=max(0,self.rival_buff_timer-dt); self.rival_fx=max(0,self.rival_fx-dt)
        self.rival_mobility_cd-=dt; self.rival_parry_cd-=dt; self.rival_parry_time=max(0.0,self.rival_parry_time-dt)
        if self.rival_character=="Vasco" and self.rival_vasco_jackpot>0:
            before=self.rival_vasco_jackpot
            self.rival_vasco_jackpot=max(0.0,self.rival_vasco_jackpot-dt)
            self.rival_vasco_particle_cd-=dt
            if self.rival_vasco_particle_cd<=0:
                game.spawn_particles(self.pos,VASCO_NEON,2); self.rival_vasco_particle_cd=0.07
            if before>0 and self.rival_vasco_jackpot<=0:
                self.rival_vasco_bet=50.0
                # So agora o Dominio pode voltar a carregar/reusar.
                self.domain_cd=random.uniform(6.5,9.0)
        self._update_rival_domain(dt,game)
        # Atualiza invocacoes/boomerangs do proprio rival.
        self.rival_minions=[m for m in self.rival_minions if m.update(dt,game)]
        self.rival_boomerangs=[b for b in self.rival_boomerangs if b.update(dt,game)]
        to=game.player.pos-self.pos; dist=max(1.0,to.length()); d=to/dist; self.facing=pygame.Vector2(d)
        # Rivais agora usam mobilidade; Kevyn tambem abre janelas de Parry como o personagem real.
        if self.rival_character=="Kevyn" and self.rival_parry_cd<=0 and self.rival_parry_time<=0:
            self.rival_parry_time=0.55; self.rival_parry_cd=random.uniform(3.6,5.2)
            game.damage_texts.append(DamageText("PARRY",pygame.Vector2(self.pos),YELLOW,0.55))
        if self.rival_mobility_cd<=0 and self.rival_dash_time<=0 and self.rival_character not in ("Glonk",):
            self.rival_dash_time=0.18 if self.rival_character!="Kevyn" else 0.24
            self.rival_dash_dir=pygame.Vector2(d)
            self.rival_mobility_cd=random.uniform(2.2,3.4)
        if self.rival_dash_time>0:
            self.rival_dash_time-=dt; self.pos += self.rival_dash_dir*self.speed*4.5*(1.75 if self.rival_character=="Vasco" and self.rival_vasco_jackpot>0 else 1.0)*dt
            if self.pos.distance_to(game.player.pos)<=self.radius+game.player.radius+S(14):
                game.player.take_damage(max(11,game.player.max_hp*0.070),game); self.rival_dash_time=0
        else:
            if self.rival_character=="Vasco" and self.rival_vasco_jackpot>0:
                old_speed=self.speed; self.speed*=1.75; self._move(dt,game,d,dist); self.speed=old_speed
            else:
                self._move(dt,game,d,dist)
        if self.rival_attack_cd<=0:self._basic_attack(game,d,dist)
        if self.rival_special_cd<=0:self._special(game,d,dist)
        self.pos.x=clamp(self.pos.x,self.radius,W-self.radius); self.pos.y=clamp(self.pos.y,S(180)+self.radius,H-S(335)-self.radius)

    def draw(self,offset):
        # Desenha o rival como Pac-Man/personagem, nao como boss generico.
        p=self.pos+offset; body=WHITE if self.flash>0 else self.color
        pygame.draw.circle(SCREEN,body,(int(p.x),int(p.y)),self.radius); pygame.draw.circle(SCREEN,WHITE,(int(p.x),int(p.y)),self.radius,max(2,S(3)))
        if self.rival_character=="Potential Man": pygame.draw.circle(SCREEN,WHITE,(int(p.x),int(p.y)),self.radius,max(2,S(5)))
        # Indicador frontal simples.
        tip=p+self.facing*S(38); pygame.draw.circle(SCREEN,DARK,(int(tip.x),int(tip.y)),max(2,S(5)))
        if self.rival_fx>0:
            if self.rival_character=="Potential Man":
                a=math.atan2(self.facing.y,self.facing.x); pts=[p,p+vec_from_angle(a-0.42)*S(220),p+vec_from_angle(a+0.42)*S(220)]; pygame.draw.polygon(SCREEN,PINK,pts,max(2,S(4)))
            elif self.rival_character=="Kevyn":
                a=math.atan2(self.facing.y,self.facing.x); r=S(135); rect=pygame.Rect(p.x-r,p.y-r,r*2,r*2)
                pygame.draw.arc(SCREEN,WHITE,rect,-(a+0.85),-(a-0.85),max(3,S(10)))
                h=p+self.facing*S(62); tip=p+self.facing*S(142); pygame.draw.line(SCREEN,(210,220,235),h,tip,max(2,S(6)))
            elif self.rival_character=="Colosso do Caos": pygame.draw.circle(SCREEN,WHITE,(int(p.x),int(p.y)),S(270),max(2,S(6)))
            elif self.rival_character=="Glonk 100% Power": pygame.draw.line(SCREEN,GREEN,p,p+self.facing*S(150),max(5,S(14)))
        if self.rival_character=="Kevyn" and self.rival_parry_time>0:
            pygame.draw.circle(SCREEN,YELLOW,(int(p.x),int(p.y)),self.radius+S(18),max(2,S(5)))
        if self.rival_character=="Vasco":
            if self.rival_vasco_jackpot>0:
                pygame.draw.circle(SCREEN,VASCO_NEON,(int(p.x),int(p.y)),self.radius+S(18),max(2,S(6)))
            bet_w=S(130); bet_y=p.y-self.radius-S(47)
            pygame.draw.rect(SCREEN,DARK,(p.x-bet_w/2,bet_y,bet_w,S(8)),border_radius=S(4))
            pygame.draw.rect(SCREEN,VASCO_NEON,(p.x-bet_w/2,bet_y,bet_w*clamp(self.rival_vasco_bet/100.0,0,1),S(8)),border_radius=S(4))
        for m in self.rival_minions:m.draw(offset)
        for b in self.rival_boomerangs:b.draw(offset)
        bw=S(150); pygame.draw.rect(SCREEN,DARK,(p.x-bw/2,p.y-self.radius-S(28),bw,S(9))); pygame.draw.rect(SCREEN,RED,(p.x-bw/2,p.y-self.radius-S(28),bw*clamp(self.hp/max(1,self.max_hp),0,1),S(9)))
        draw_text(self.name,FONT_S,self.color,(p.x,p.y+self.radius+S(28)),True)


class Game:
    def __init__(self):
        self.state = "menu"
        self.mode = "arena"  # "arena" ou "afk"
        self.selected_character = "Ycaro"
        self.selection_target = "arena"
        self.difficulty = "easy"
        self.pending_character = None
        self.difficulty_rects = []
        self.game_mode = "normal"
        self.pending_game_mode = "normal"
        self.game_mode_rects = []
        self.infinite_curses = []
        self.curse_choice_cards = []
        self.curse_choice_rects = []
        self.boss_heritages = []
        self.boss_rush_index = 0
        self.one_vs_all_roster = []
        self.one_vs_all_index = 0
        self.evolution_traits = []
        self.rogue_rule = None
        self.arena_spawn_timer = 0.0
        self.arena_hazard_timer = 8.0
        self.arena_hazards = []
        self.arena_next_reward = 15
        self.arena_reward_cards = []
        self.arena_reward_rects = []
        self.arena_inset = 0.0
        self.hunt_glonk_transform_count = 0
        self.hunt_swap_timer = 4.0
        self.mode_complete_title = ""
        self.mode_complete_subtitle = ""
        self.character_tab = "characters"
        self.character_carousel_index = CHARACTER_ORDER.index("Ycaro")
        self.character_swipe_start = None
        self.character_swipe_current = None
        self.character_swipe_finger = None
        self.character_stat_plus_rects = []
        self.evolution_notice = ""
        self.evolution_notice_timer = 0.0
        self.upgrade_return_mode = "arena"
        self.player = Player(self, self.selected_character)
        self.enemies = []
        self.projectiles = []
        self.summons = []
        self.servants = []
        self.ruan_guardian = None
        self.drops = []
        self.particles = []
        self.damage_texts = []
        self.wave = 1
        self.kills = 0
        self.score = 0
        self.run_coins = 0
        self.run_rewards_banked = False
        self.combo = 0
        self.combo_timer = 0
        self.domain_charge = 0
        # Contexto temporario de recarga: 20 bruto / 5 = 4%, alvo de ~25 ataques completos.
        self.current_domain_charge_raw_override = None
        self.domain_active = False
        self.domain_timer = 0.0
        self.domain_duration = 8.0
        self.domain_center = pygame.Vector2(W/2, H/2)
        self.domain_radius = S(562.5)
        # V8: sem cutscene/overlay de dominio. Apenas mensagem curta + efeito.
        self.domain_cutscene_timer = 0.0
        self.domain_cutscene_total = 0.0
        self.domain_pending = False
        self.domain_name = ""
        self.domain_message_timer = 0.0
        self.lira_domain_selected=[]
        self.lira_domain_choice_rects=[]
        self.kayk_domain_fire_cd = 0.0
        self.boss_domain_message = ""
        self.boss_domain_message_timer = 0.0
        self.domain_clash_active = False
        self.domain_clash_timer = 0.0
        self.domain_clash_score = 0.0
        self.domain_clash_boss = None
        self.clash_result = ""
        self.clash_result_timer = 0.0
        self.perfect_dodges = 0
        self.parries = 0
        self.start_ticks = pygame.time.get_ticks()
        self.time = 0
        self.slash_fx = 0
        self.flash_screen = 0
        self.shake = 0
        self.event_name = None
        self.enemy_speed_mult = 1.0
        self.coin_multiplier = 1.0
        self.enemy_damage_mult = 1.0
        self.player_event_damage_mult = 1.0
        self.enemy_perma_speed_mult = 1.0
        self.upgrade_cards = []
        self.selected_upgrade_card = None
        self.achievement = ""
        self.achievement_timer = 0
        self.move_touch = {"up": False, "down": False, "left": False, "right": False}
        self.active_fingers = {}
        self.joystick_vector = pygame.Vector2()
        self.joystick_finger = None
        self.joystick_mouse_active = False
        # V14 FINAL: Kayk/Ycaro/Pedro usam o antigo ATK como segundo analogico de mira.
        self.aim_vector = pygame.Vector2(1, 0)
        self.aim_finger = None
        self.aim_mouse_active = False
        self.aim_active = False
        self.buttons = self.make_buttons()
        self.afk_buttons = self.make_afk_buttons()
        self.wave_banner = 0
        self.wave_clear_lock = False
        self.owned_upgrades = set()
        self.owned_upgrade_counts = {}
        self.synergies = set()
        self.catalog_page = 0
        self.upgrade_catalog_tab = "found"
        self.bestiary_page = 0
        self.passive_catalog_page = 0
        self.passive_catalog_tab = "known"
        self.passive_roll_character = "Ycaro"
        self.passive_roll_return_state = "character_select"
        self.passive_roll_page = 0
        self.passive_roll_slot = 0
        self.passive_roll_result = None
        self.passive_roll_display_key = None
        self.passive_roll_message = ""
        self.passive_roll_anim = 0.0
        self.passive_roll_spinning = False
        self.passive_roll_sequence = []
        self.passive_roll_sequence_index = 0
        self.passive_roll_tick = 0.0
        self.passive_roll_final_key = None
        self.passive_roll_scroll_pos = 0.0
        self.passive_roll_elapsed = 0.0
        self.passive_roll_duration = 5.4
        self.passive_roll_last_center_index = 0
        self.passive_catalog_return_state = "menu"
        self.passive_auto_mode = False
        self.passive_auto_delay = 0.0
        self.passive_auto_warning = False
        self.passive_auto_config_page = 0
        self.passive_auto_config_return = "passive_roll"
        self.passive_dev_character = "Ycaro"
        self.passive_dev_slot = 0
        self.passive_dev_page = 0
        self.run_upgrade_page = 0
        self.shop_page = 0
        self.forge_page = 0
        self.forge_character_index = 0
        self.items_page = 0
        self.items_tab = "materials"
        self.whats_new_scroll = 0.0
        self.whats_new_version = "V15"
        self.whats_new_drag_start = None
        self.whats_new_scroll_start = 0.0
        self.whats_new_max_scroll = 0.0
        self.whats_new_overscroll = S(95)
        self.settings_return_state = "menu"
        self.settings_drag = None
        self.settings_dirty = False
        self.weapons_page = 0
        self.weapons_character_index = 0
        self.forge_fire_trails = []
        self.achievement_page = 0
        self.mission_character_index = 0
        self.cheat_buffer = ""
        self.cheat_message = ""
        self.cheat_money_mode = False
        self.cheat_money_buffer = ""
        self.cheat_value_mode = None
        self.cheat_extra_rects = []
        self.backup_code = ""
        self.backup_input = ""
        self.backup_message = ""
        self.backup_input_active = False
        self.ambient_heal_orb_timer = random.uniform(5.0, 9.0)
        self.control_edit_drag_key = None
        self.control_edit_drag_offset = pygame.Vector2()
        self.synergy_name = ""
        self.synergy_timer = 0.0
        self.enemy_slow_timer = 0.0
        self.delayed_blasts = []
        self.current_damage_kind = None
        self.healing_locked = False
        self.extinction_hp_cap = None
        self.attack_held = False
        self.parry_held = False
        self.domain_held = False
        self.dash_held = False
        self.orbital_anas = []
        self.planted_pineapples = []
        self.divine_burst_fx = None
        self.sin_sloth_slow = False
        self.orb_chain_count = 0
        self.orb_chain_timer = 0.0
        self.kevyn_sword_kills = 0
        self.kevyn_sword_kill_timer = 0.0
        self.unlock_notice = ""
        self.unlock_notice_timer = 0.0
        self.father_wave_fx_timer = 0.0
        self.father_wave_fx_total = 0.48
        self.father_wave_fx_center = pygame.Vector2()
        self.father_wave_fx_radius = 0.0
        self.devoured_by_gula = False
        self.gula_death_hunger = 0
        # Sans / BAD TIME
        self.bad_time_active = False
        self.parry_held=False; self.domain_held=False; self.dash_held=False
        self.orbital_anas=[]; self.planted_pineapples=[]; self.divine_burst_fx=None; self.sin_sloth_slow=False
        self.hank_artillery_queue=[]; self.hank_domain_active=False; self.hank_domain_trapped_ids=set(); self.hank_explosions=[]; self.hank_cannon_pos=None
        self.bad_time_bone_cd = 0.0
        self.bad_time_obstacle_cd = 0.0
        self.sans_bones = []
        self.sans_blaster_fx = []
        self.mass_hit_fx = False
        # Potential Man / shikigamis
        self.potential_summons = []
        self.hank_artillery_queue = []
        self.hank_domain_active = False
        self.hank_domain_trapped_ids = set()
        self.hank_explosions = []
        self.hank_cannon_pos = None
        self.mahoraga = None
        self.mahoraga_hostile_to_dogs = False
        # Cutscene da invocacao do Mahoraga. Timeline definida pelo usuario:
        # 1.8s FURUBE | 3.5s YURA YURA | 8.0s corredor de lobos | 15.0s CLANK | fim em 16.0s.
        # Usa relogio absoluto do Pygame em vez de acumular dt para nao ficar presa no Android.
        self.mahoraga_cutscene_active = False
        self.mahoraga_cutscene_t = 0.0
        self.mahoraga_cutscene_duration = 16.0
        self.mahoraga_cutscene_start_ms = 0
        self.mahoraga_cutscene_reveal_t = 13.25
        self.mahoraga_cutscene_clank_t = 15.0
        self.mahoraga_cutscene_revealed = False
        self.mahoraga_cutscene_clanked = False
        self.mahoraga_cutscene_wolf_pairs = 0
        # Sukuna / FUUGA: primeiro toque marca, segundo confirma e inicia a cutscene.
        self.sukuna_ult_marked = False
        self.sukuna_ult_center = pygame.Vector2(W/2, H/2)
        self.sukuna_ult_radius = S(562.5)
        self.sukuna_cutscene_active = False
        self.sukuna_cutscene_start_ms = 0
        self.sukuna_cutscene_t = 0.0
        self.sukuna_cutscene_duration = 10.0
        self.sukuna_destruction_active = False
        self.sukuna_destruction_timer = 0.0
        self.sukuna_fuuga_fx = None
        self.sukuna_domain_tick_cd = 0.0
        self.vinicius_turrets=[]; self.vinicius_walls=[]; self.vinicius_rocks=[]
        self.vinicius_scrap=0; self.vinicius_mini_kills=0; self.vinicius_mega_pending=False; self.vinicius_mega_choice_rects=[]
        self.training_target_name=None; self.training_respawn_timer=0.0; self.bestiary_train_rects=[]
        self.glonk_event_timer=0.0; self.glonk_event_stage=None; self.glonk_boss_intro_timer=0.0; self.glonk_music_cut_timer=0.0
        self.sync_saved_achievements()

    def mark_sukuna_ult(self):
        if self.player.character != SUKUNA_KEY or self.domain_charge < 100:
            return False
        d=pygame.Vector2(self.player.facing) if self.player.facing.length_squared() else pygame.Vector2(1,0)
        d=d.normalize()
        edge=ray_to_arena_edge(self.player.pos,d)
        max_dist=max(S(160),(edge-self.player.pos).length())
        travel=min(S(520),max(S(190),max_dist*0.58))
        c=self.player.pos+d*travel
        top=S(165); bottom=H-S(335)
        c.x=clamp(c.x,S(70),W-S(70)); c.y=clamp(c.y,top+S(55),bottom-S(55))
        self.sukuna_ult_center=pygame.Vector2(c)
        self.sukuna_ult_marked=True
        self.damage_texts.append(DamageText("FUUGA: AREA MARCADA",pygame.Vector2(self.player.pos),SUKUNA_FIRE,1.0))
        AUDIO.play("click",0.8,80)
        return True

    def start_sukuna_cutscene(self):
        if self.player.character != SUKUNA_KEY or self.sukuna_cutscene_active or not self.sukuna_ult_marked:
            return False
        self.sukuna_cutscene_active=True
        self.sukuna_cutscene_start_ms=pygame.time.get_ticks()
        self.sukuna_cutscene_t=0.0
        self.attack_held=False; self.parry_held=False; self.domain_held=False; self.dash_held=False
        self.aim_active=False; self.aim_finger=None; self.aim_mouse_active=False
        self.joystick_vector.update(0,0)
        AUDIO._stop_music_everywhere()
        if AUDIO.sfx_on:
            if not AUDIO.play_external_once("sukuna_ult",AUDIO.sfx_volume):
                AUDIO.play("domain",1.0,250)
        return True

    def sukuna_cutscene_elapsed(self):
        if not self.sukuna_cutscene_active:
            return self.sukuna_cutscene_t
        return max(0.0,(pygame.time.get_ticks()-self.sukuna_cutscene_start_ms)/1000.0)

    def trigger_sukuna_fuuga(self):
        center=pygame.Vector2(self.sukuna_ult_center)
        radius=self.sukuna_ult_radius*(1.20 if self.player.sukuna_open_furnace else 1.0)
        old=self.current_damage_kind; self.current_damage_kind="sukuna_fuuga"
        for e in list(self.enemies):
            if not e.dead and e.pos.distance_to(center)<=radius+e.radius:
                dmg=self.player.base_damage*6.5*(1.35 if self.player.sukuna_open_furnace else 1.0)*self.player.effective_damage_mult(self,e,"sukuna_fuuga",e.pos.distance_to(self.player.pos))
                e.damage(dmg,self,center)
        maho=getattr(self,"mahoraga",None)
        if maho is not None and not maho.dead and maho.pos.distance_to(center)<=radius+maho.radius:
            dmg=self.player.base_damage*6.5*(1.35 if self.player.sukuna_open_furnace else 1.0)*self.player.effective_damage_mult(self,None,"sukuna_fuuga",maho.pos.distance_to(self.player.pos))
            maho.take_damage(dmg,self,center,from_player=True)
        self.current_damage_kind=old
        self.spawn_particles(center,SUKUNA_FIRE,42)
        self.spawn_particles(center,ORANGE,34)
        self.shake=max(self.shake,S(24)); self.flash_screen=max(self.flash_screen,0.18)
        self.sukuna_fuuga_fx={"start":pygame.Vector2(self.player.pos),"end":center,"radius":radius,"timer":1.45,"total":1.45}

    def finish_sukuna_cutscene(self):
        if not self.sukuna_cutscene_active:
            return
        self.sukuna_cutscene_active=False
        self.sukuna_cutscene_t=self.sukuna_cutscene_duration
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        AUDIO.current_track=None
        self.trigger_sukuna_fuuga()
        self.sukuna_ult_marked=False
        self.sukuna_destruction_active=True
        self.sukuna_destruction_timer=3.85
        if AUDIO.sfx_on:
            if not AUDIO.play_external_once("sukuna_destruction",AUDIO.sfx_volume):
                AUDIO.play("hank_blast",1.0,100)

    def update_sukuna_cutscene(self,dt):
        if not self.sukuna_cutscene_active:
            return
        t=self.sukuna_cutscene_elapsed(); self.sukuna_cutscene_t=t
        if t>=self.sukuna_cutscene_duration:
            self.finish_sukuna_cutscene()

    def update_sukuna_destruction(self,dt):
        if not self.sukuna_destruction_active:
            return
        self.sukuna_destruction_timer=max(0.0,self.sukuna_destruction_timer-dt)
        if self.sukuna_fuuga_fx is not None:
            self.sukuna_fuuga_fx["timer"]-=dt
            if self.sukuna_fuuga_fx["timer"]<=0:
                self.sukuna_fuuga_fx=None
        if self.sukuna_destruction_timer<=0:
            self.sukuna_destruction_active=False
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            AUDIO.current_track=None

    def draw_sukuna_cutscene(self):
        t=self.sukuna_cutscene_elapsed(); self.sukuna_cutscene_t=t
        if t>=self.sukuna_cutscene_duration+0.30:
            self.finish_sukuna_cutscene(); self.draw_playing(); return
        SCREEN.fill((4,3,4))
        # moldura escura de arena para manter a referencia espacial sem mostrar a HUD/botoes.
        arena=pygame.Rect(S(24),S(110),W-S(48),H-S(180))
        pygame.draw.rect(SCREEN,(9,7,8),arena,border_radius=S(22)); pygame.draw.rect(SCREEN,(40,26,22),arena,max(2,S(3)),border_radius=S(22))
        # Zoom progressivo: aproxima rapido e segura no rosto/corpo do Sukuna.
        zoom=1.0+0.95*min(1.0,max(0.0,t/1.7))
        if t>9.25:
            zoom*=1.0-0.20*min(1.0,(t-9.25)/0.75)
        c=pygame.Vector2(W/2,H/2+S(35)); rr=max(S(30),int(self.player.radius*zoom*1.55))
        # fogo/particulas: orbitam e sobem para sugerir chamas sem depender do update normal da arena.
        for i in range(30):
            phase=i*0.73+t*(1.7+(i%5)*0.12)
            rad=S(42)+(i%7)*S(10)
            x=c.x+math.cos(phase)*rad*zoom*0.75
            y=c.y+math.sin(phase*0.61)*rad*0.45-(t*38+i*17)%S(150)
            size=max(2,S(3)+(i%4)*S(2))
            col=SUKUNA_FIRE if i%3 else YELLOW
            pygame.draw.circle(SCREEN,col,(int(x),int(y)),size)
        pygame.draw.circle(SCREEN,SUKUNA_COLOR,(int(c.x),int(c.y)),rr)
        pygame.draw.circle(SCREEN,(255,186,125),(int(c.x),int(c.y)),rr,max(2,S(5)))
        d=self.player.facing.normalize() if self.player.facing.length_squared() else pygame.Vector2(1,0)
        pygame.draw.line(SCREEN,DARK,c,c+d*rr*1.15,max(2,S(7)))
        # fala do personagem, nao texto solto no centro.
        if t>=1.0:
            bw=S(330); bh=S(82); bubble=pygame.Rect(int(c.x-bw/2),int(c.y-rr-S(125)),bw,bh)
            pygame.draw.rect(SCREEN,(18,12,10),bubble,border_radius=S(18)); pygame.draw.rect(SCREEN,SUKUNA_FIRE,bubble,max(2,S(4)),border_radius=S(18))
            tail=[(int(c.x-S(18)),bubble.bottom),(int(c.x+S(20)),bubble.bottom),(int(c.x),bubble.bottom+S(28))]
            pygame.draw.polygon(SCREEN,(18,12,10),tail); pygame.draw.lines(SCREEN,SUKUNA_FIRE,False,tail+[tail[0]],max(2,S(3)))
            draw_text("FUUGA---",FONT_L,SUKUNA_FIRE,bubble.center,True)
        # alvo marcado aparece fantasmagorico no fundo para lembrar onde o ataque caira.
        target=pygame.Vector2(W*0.78,H*0.52); pulse=0.65+0.35*math.sin(t*4.2)
        pygame.draw.circle(SCREEN,(105,40,20),(int(target.x),int(target.y)),int(S(120)*pulse),max(2,S(4)))

    def start_mahoraga_cutscene(self):
        if self.player.character != "Potential Man" or self.mahoraga_cutscene_active:
            return False
        self.mahoraga_cutscene_active = True
        self.mahoraga_cutscene_t = 0.0
        self.mahoraga_cutscene_start_ms = pygame.time.get_ticks()
        self.mahoraga_cutscene_revealed = False
        self.mahoraga_cutscene_clanked = False
        self.mahoraga_cutscene_wolf_pairs = 0
        self.mahoraga = None
        self.mahoraga_hostile_to_dogs = False
        self.attack_held=False; self.parry_held=False; self.domain_held=False; self.dash_held=False
        self.aim_active=False; self.aim_finger=None; self.aim_mouse_active=False
        self.joystick_vector.update(0,0); self.aim_vector.update(0,0)
        # A luta e os controles ficam congelados durante a invocacao.
        # O arquivo mahoraga_summon.ogg tem 16s e toca uma unica vez.
        AUDIO._stop_music_everywhere()
        if AUDIO.sfx_on:
            if not AUDIO.play_external_once("mahoraga_summon", AUDIO.sfx_volume):
                AUDIO.play("domain",1.0,250)
        return True

    def mahoraga_cutscene_elapsed(self):
        if not self.mahoraga_cutscene_active:
            return self.mahoraga_cutscene_t
        # Relogio absoluto: mais robusto no Android/Pydroid que somar dt frame a frame.
        if self.mahoraga_cutscene_start_ms <= 0:
            self.mahoraga_cutscene_start_ms = pygame.time.get_ticks()
        return max(0.0, (pygame.time.get_ticks()-self.mahoraga_cutscene_start_ms)/1000.0)

    def _spawn_mahoraga_for_cutscene(self):
        if self.mahoraga is not None and not getattr(self.mahoraga,"dead",False):
            return self.mahoraga
        spawn = pygame.Vector2(W*0.50, S(300))
        maho = MahoragaSummon(spawn, self.player, self.wave)
        if getattr(self.player,"potential_early_wheel",False):
            maho.resistance=0.20; maho.player_damage_adaptation=0.20; maho.wave_adaptations=2
        if getattr(self.player,"potential_ten_shadows_general",False):
            maho.damage*=1.40; maho.speed*=1.15
        self.potential_summons.append(maho)
        self.mahoraga = maho
        self.mahoraga_hostile_to_dogs = False
        return maho

    def finish_mahoraga_cutscene(self):
        # Safety finish: nunca deixa a tela escura prender o jogador indefinidamente.
        maho = self._spawn_mahoraga_for_cutscene()
        if not self.mahoraga_cutscene_clanked:
            self.mahoraga_cutscene_clanked = True
            maho.adapt(self, 0.10, heal=False, announce=False)
        self.mahoraga_cutscene_active = False
        self.mahoraga_cutscene_t = self.mahoraga_cutscene_duration
        self.domain_name="MAHORAGA"
        self.domain_message_timer=1.8
        self.attack_held=False; self.parry_held=False; self.domain_held=False; self.dash_held=False
        self.aim_active=False; self.aim_finger=None; self.aim_mouse_active=False
        self.joystick_vector.update(0,0); self.aim_vector.update(0,0)
        self.damage_texts.append(DamageText("MAHORAGA INVOCADO",pygame.Vector2(maho.pos),YELLOW,1.1))
        self.damage_texts.append(DamageText("ADAPTACAO 10%",pygame.Vector2(maho.pos.x,maho.pos.y-S(62)),YELLOW,1.1))
        self.shake=max(self.shake,S(18))
        # Forca o AudioManager a escolher a trilha de batalha do Mahoraga no mesmo frame.
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        AUDIO.current_track = None

    def update_mahoraga_cutscene(self, dt):
        if not self.mahoraga_cutscene_active:
            return
        t = self.mahoraga_cutscene_elapsed()
        self.mahoraga_cutscene_t = t

        # A partir dos 8s os lobos aparecem 2 por 2, formando um corredor em cone.
        if t >= 8.0:
            self.mahoraga_cutscene_wolf_pairs = min(7, 1 + int((t-8.0)/0.72))

        # Quando o corredor termina, Mahoraga aparece ao fundo com a roda ainda parada.
        if t >= self.mahoraga_cutscene_reveal_t and not self.mahoraga_cutscene_revealed:
            self.mahoraga_cutscene_revealed = True
            self._spawn_mahoraga_for_cutscene()
            self.shake=max(self.shake,S(8))

        # 15.0s: CLANK. A roda gira e a primeira adaptacao acontece exatamente aqui.
        if t >= self.mahoraga_cutscene_clank_t and not self.mahoraga_cutscene_clanked:
            self.mahoraga_cutscene_clanked = True
            maho = self._spawn_mahoraga_for_cutscene()
            maho.adapt(self, 0.10, heal=False, announce=False)
            self.flash_screen=max(self.flash_screen,0.18)
            self.shake=max(self.shake,S(28))

        # O audio foi cortado em 16s. Quando termina, a luta volta imediatamente.
        if t >= self.mahoraga_cutscene_duration:
            self.finish_mahoraga_cutscene()

    def draw_mahoraga_cutscene(self):
        # Mesmo o draw recalcula o tempo absoluto. Se houver um frame de update perdido no Android,
        # a cutscene continua visualmente sincronizada e possui uma saida de seguranca.
        t = self.mahoraga_cutscene_elapsed()
        self.mahoraga_cutscene_t = t
        if t >= self.mahoraga_cutscene_duration + 0.35:
            self.finish_mahoraga_cutscene()
            self.draw_playing()
            return

        self.draw_bg()
        offset = self.camera_offset()
        # Potential Man continua visivel; inimigos, projeteis e botoes somem durante a invocacao.
        self.player.draw(offset, self)
        darkness = pygame.Surface((W,H), pygame.SRCALPHA)
        darkness.fill((0,0,0,218))
        SCREEN.blit(darkness,(0,0))

        p = self.player.pos + offset

        def speech_bubble(text):
            # Fala do personagem em vez de mensagem gigante no centro da tela.
            pad=S(18); bw=max(S(190), FONT_M.size(text)[0]+pad*2); bh=S(68)
            bx=clamp(p.x-bw/2,S(20),W-bw-S(20)); by=max(S(55),p.y-self.player.radius-S(105))
            bubble=pygame.Surface((int(bw),int(bh)),pygame.SRCALPHA)
            pygame.draw.rect(bubble,(8,8,12,230),(0,0,int(bw),int(bh)),border_radius=S(16))
            pygame.draw.rect(bubble,(235,235,245,235),(0,0,int(bw),int(bh)),max(2,S(3)),border_radius=S(16))
            SCREEN.blit(bubble,(int(bx),int(by)))
            tail=[(int(p.x-S(12)),int(by+bh)),(int(p.x+S(12)),int(by+bh)),(int(p.x),int(by+bh+S(22)))]
            pygame.draw.polygon(SCREEN,(235,235,245),tail)
            pygame.draw.polygon(SCREEN,(8,8,12),[(tail[0][0]+S(4),tail[0][1]),(tail[1][0]-S(4),tail[1][1]),(tail[2][0],tail[2][1]-S(5))])
            draw_text(text,FONT_M,WHITE,(bx+bw/2,by+bh/2),True)

        # Timeline pedida: 1.8s FURUBE ate 3.5s; 3.5s YURA YURA ate 7.0s.
        if 1.80 <= t < 3.50:
            speech_bubble("FURUBE")
        elif 3.50 <= t < 7.00:
            speech_bubble("YURA YURA")

        def draw_wolf(cx, cy, scale=1.0, mirror=1):
            r=max(S(16),int(S(31)*scale)); c=(225,225,235)
            pygame.draw.circle(SCREEN,c,(int(cx),int(cy)),r)
            pts1=[(cx-r*.70,cy-r*.50),(cx-r*.24,cy-r*1.28),(cx-r*.02,cy-r*.56)]
            pts2=[(cx+r*.70,cy-r*.50),(cx+r*.24,cy-r*1.28),(cx+r*.02,cy-r*.56)]
            pygame.draw.polygon(SCREEN,c,[(int(x),int(y)) for x,y in pts1]); pygame.draw.polygon(SCREEN,c,[(int(x),int(y)) for x,y in pts2])
            pygame.draw.circle(SCREEN,RED,(int(cx-r*.30),int(cy-r*.04)),max(2,S(3)))
            pygame.draw.circle(SCREEN,RED,(int(cx+r*.30),int(cy-r*.04)),max(2,S(3)))

        # Corredor em cone. Cada etapa adiciona um par de lobos; as fileiras convergem para Mahoraga.
        pair_count = min(7, max(0, self.mahoraga_cutscene_wolf_pairs))
        if t >= 8.0:
            # Guias discretas deixam claro o corredor sem competir com os personagens.
            guide=pygame.Surface((W,H),pygame.SRCALPHA)
            pygame.draw.line(guide,(220,220,235,34),(int(W*.18),int(H*.72)),(int(W*.45),int(H*.31)),max(1,S(2)))
            pygame.draw.line(guide,(220,220,235,34),(int(W*.82),int(H*.72)),(int(W*.55),int(H*.31)),max(1,S(2)))
            SCREEN.blit(guide,(0,0))
            for i in range(pair_count):
                f=i/6.0
                y=H*(0.70-0.34*f)
                left_x=W*(0.22+0.22*f)
                right_x=W*(0.78-0.22*f)
                sc=1.0-0.34*f
                draw_wolf(left_x,y,sc,-1); draw_wolf(right_x,y,sc,1)

        # Mahoraga aparece quando o corredor chega ao fim, antes do CLANK.
        if self.mahoraga_cutscene_revealed and self.mahoraga is not None:
            mp=self.mahoraga.pos+offset
            # Corpo ao fundo.
            pygame.draw.circle(SCREEN,self.mahoraga.color,(int(mp.x),int(mp.y)),self.mahoraga.radius)
            pygame.draw.circle(SCREEN,DARK,(int(mp.x),int(mp.y)),self.mahoraga.radius,max(2,S(5)))
            # Roda do Dharma dedicada da cutscene. Ela possui um marcador assimetrico para
            # que o giro de um dente (45 graus) seja VISIVEL — sem isso os 8 raios iguais
            # terminavam numa figura identica e no celular parecia que a roda nao girava.
            wc=pygame.Vector2(mp.x,mp.y-self.mahoraga.radius-S(60)); wr=S(62)
            turn=0.0
            spin_progress=0.0
            if t >= self.mahoraga_cutscene_clank_t:
                spin_progress=clamp((t-self.mahoraga_cutscene_clank_t)/0.58,0.0,1.0)
                # easing rapido no inicio e assentamento no novo encaixe
                eased=1.0-(1.0-spin_progress)**3
                turn=eased*(math.pi/4)
            pygame.draw.circle(SCREEN,YELLOW,(int(wc.x),int(wc.y)),wr,max(2,S(5)))
            pygame.draw.circle(SCREEN,YELLOW,(int(wc.x),int(wc.y)),S(10),max(2,S(3)))
            for i in range(8):
                ang=i*math.tau/8+turn
                d=vec_from_angle(ang)
                a=wc+d*S(12); b=wc+d*wr
                width=max(2,S(6) if i==0 else S(4))
                pygame.draw.line(SCREEN,YELLOW,(int(a.x),int(a.y)),(int(b.x),int(b.y)),width)
                # pequenos pinos nas pontas reforcam a leitura da rotacao
                pygame.draw.circle(SCREEN,YELLOW,(int(b.x),int(b.y)),max(2,S(4)))
            # Marcador unico preso ao primeiro raio: acompanha o giro exatamente no CLANK.
            marker_d=vec_from_angle(turn)
            marker=wc+marker_d*(wr+S(9))
            pygame.draw.circle(SCREEN,ORANGE,(int(marker.x),int(marker.y)),max(3,S(8)))
            pygame.draw.circle(SCREEN,WHITE,(int(marker.x),int(marker.y)),max(2,S(3)))
            if t >= self.mahoraga_cutscene_clank_t:
                pulse=1.0-min(1.0,(t-self.mahoraga_cutscene_clank_t)/0.7)
                rr=int(S(90)+S(220)*(1.0-pulse))
                pygame.draw.circle(SCREEN,YELLOW,(int(wc.x),int(wc.y)),rr,max(2,S(7)))
                draw_text("CLANK!",FONT_L,WHITE,(W/2,H*0.18),True)
                if self.mahoraga_cutscene_clanked:
                    draw_text("ADAPTACAO 10%",FONT_M,YELLOW,(W/2,H*0.25),True)

    def make_buttons(self):
        b = {}
        # V12: controles ficam dentro de uma zona segura maior para notch/gestos.
        bounds = pygame.Rect(CONTROL_SAFE_X, CONTROL_SAFE_Y, W-CONTROL_SAFE_X*2, H-CONTROL_SAFE_Y*2)
        bottom = H - CONTROL_SAFE_Y - S(30)

        # Joystick analogico inferior esquerdo.
        joy = max(S(250), min(S(335), int(H * 0.30)))
        b["joystick"] = pygame.Rect(CONTROL_SAFE_X + S(24), bottom - joy, joy, joy)

        # Acoes inferior direito, afastadas das bordas fisicas.
        attack = max(S(155), min(S(195), int(H * 0.178)))
        small = max(S(126), min(S(158), int(attack * 0.80)))
        domain_size = max(S(118), min(S(146), int(attack * 0.74)))
        action_gap = max(S(28), int(attack * 0.16))
        ax = W - CONTROL_SAFE_X - S(30) - attack
        ay = bottom - attack
        b["attack"] = pygame.Rect(ax, ay, attack, attack)
        sx = ax - action_gap - small
        b["dash"] = pygame.Rect(sx, bottom-small, small, small)
        b["parry"] = pygame.Rect(sx, bottom-small*2-action_gap, small, small)
        b["domain"] = pygame.Rect(ax + (attack-domain_size)//2, ay-action_gap-domain_size, domain_size, domain_size)

        pw, ph = S(160), S(66)
        b["pause"] = pygame.Rect(W//2-pw//2, CONTROL_SAFE_Y+S(12), pw, ph)

        # Layout salvo antigo continua funcionando para acoes; o joystick ganha posicao propria.
        layout = SAVE.get("control_layout", {})
        if isinstance(layout, dict):
            for key, data in layout.items():
                if key not in b or not isinstance(data, (list, tuple)) or len(data) != 4:
                    continue
                try:
                    cx, cy, rw, rh = [float(v) for v in data]
                    ww = max(S(58), int(rw * W))
                    hh = max(S(58), int(rh * H))
                    rect = pygame.Rect(0, 0, ww, hh)
                    rect.center = (int(cx*W), int(cy*H))
                    rect.clamp_ip(bounds)
                    b[key] = rect
                except Exception:
                    pass
        return b

    def make_afk_buttons(self):
        # Bancada de testes compacta no alto; nao disputa espaco com os controles.
        labels = ["DUMMY", "INIMIGO", "BOSS", "TIRO", "DOM", "UP"]
        gap = max(S(10), int(W * 0.006))
        bw = max(S(135), min(S(205), int(W * 0.085)))
        bh = max(S(54), min(S(70), int(H * 0.060)))
        total = bw * len(labels) + gap * (len(labels)-1)
        x = W/2 - total/2
        y = CONTROL_SAFE_Y + S(120)
        out = {}
        for label in labels:
            out[label] = pygame.Rect(int(x), y, bw, bh)
            x += bw + gap
        return out

    def save_control_layout(self):
        SAVE["control_layout"] = {
            key: [rect.centerx/W, rect.centery/H, rect.w/W, rect.h/H]
            for key, rect in self.buttons.items()
        }
        save_data(SAVE)

    def reset_control_layout(self):
        SAVE["control_layout"] = {}
        save_data(SAVE)
        self.buttons = self.make_buttons()
        AUDIO.play("click", 0.7)

    def resize_controls(self, factor):
        bounds = pygame.Rect(CONTROL_SAFE_X, CONTROL_SAFE_Y, W-CONTROL_SAFE_X*2, H-CONTROL_SAFE_Y*2)
        for key, rect in list(self.buttons.items()):
            if key == "pause":
                min_size = S(54)
            elif key == "joystick":
                min_size = S(180)
            else:
                min_size = S(70)
            nw = max(min_size, min(int(rect.w*factor), int(W*0.22)))
            nh = max(min_size, min(int(rect.h*factor), int(H*0.28)))
            nr = pygame.Rect(0, 0, nw, nh)
            nr.center = rect.center
            nr.clamp_ip(bounds)
            self.buttons[key] = nr
        self.save_control_layout()

    def control_editor_down(self, pos):
        if hasattr(self, "control_back_rect") and self.control_back_rect.collidepoint(pos):
            self.save_control_layout(); self.state = "menu"; return
        if hasattr(self, "control_reset_rect") and self.control_reset_rect.collidepoint(pos):
            self.reset_control_layout(); return
        if hasattr(self, "control_plus_rect") and self.control_plus_rect.collidepoint(pos):
            self.resize_controls(1.10); return
        if hasattr(self, "control_minus_rect") and self.control_minus_rect.collidepoint(pos):
            self.resize_controls(0.90); return
        # Prioriza botoes menores quando houver sobreposicao acidental.
        hits = [(key, rect) for key, rect in self.buttons.items() if rect.collidepoint(pos)]
        if hits:
            key, rect = min(hits, key=lambda item: item[1].w*item[1].h)
            self.control_edit_drag_key = key
            self.control_edit_drag_offset = pygame.Vector2(pos) - pygame.Vector2(rect.center)

    def control_editor_motion(self, pos):
        key = self.control_edit_drag_key
        if not key or key not in self.buttons:
            return
        rect = self.buttons[key]
        center = pygame.Vector2(pos) - self.control_edit_drag_offset
        rect.center = (int(center.x), int(center.y))
        rect.clamp_ip(pygame.Rect(CONTROL_SAFE_X, CONTROL_SAFE_Y, W-CONTROL_SAFE_X*2, H-CONTROL_SAFE_Y*2))

    def control_editor_up(self):
        if self.control_edit_drag_key:
            self.control_edit_drag_key = None
            self.save_control_layout()

    def reset_run(self, character=None, difficulty=None):
        chosen = character or self.selected_character
        chosen_difficulty = difficulty or getattr(self, "difficulty", "easy")
        chosen_game_mode = getattr(self, "game_mode", "normal")
        # ROGUE ignora a escolha de personagem: sorteia entre personagens normais desbloqueados.
        if chosen_game_mode == "rogue" and getattr(self,"state","") != "difficulty_select":
            candidates=[c for c in CHARACTER_ORDER if self.character_unlocked(c) and c != "Glonk"]
            if candidates: chosen=random.choice(candidates)
        self.__init__()
        self.game_mode = chosen_game_mode if chosen_game_mode in GAME_MODES else "normal"
        self.pending_game_mode = self.game_mode
        self.selected_character = chosen
        self.difficulty = chosen_difficulty if chosen_difficulty in DIFFICULTIES else "easy"
        self.state = "playing"
        self.mode = "arena"
        self.player = Player(self, chosen)
        self.start_ticks = pygame.time.get_ticks()
        self.add_mission_progress("runs", 1)
        if SAVE.get("cheat_dev", False):
            self.wave = max(1, int(SAVE.get("cheat_start_wave", 1) or 1))
        # Identidade inicial de cada modo.
        if self.game_mode == "extinction":
            self.healing_locked = True
            self.player.damage_mult *= 1.55
            self.player.max_hp *= 1.30; self.player.hp=self.player.max_hp
            self.player.max_stamina *= 1.25; self.player.stamina=self.player.max_stamina
            self.player.crit_chance += 0.15; self.player.projectile_pierce += 1; self.player.shield += 2
            self.extinction_hp_cap = self.player.hp
            self.damage_texts.append(DamageText("EXTINCAO: CURA ZERO ABSOLUTA",pygame.Vector2(self.player.pos),RED,1.4))
        elif self.game_mode == "one_vs_all":
            self.one_vs_all_roster=[c for c in CHARACTER_ORDER+BETA_CHARACTER_ORDER if c!=chosen]
            self.one_vs_all_index=0
        elif self.game_mode == "rogue":
            cards=self.generate_upgrades(1)
            if cards:
                self.suppress_upgrade_advance=True; self.upgrade_return_mode="arena"; self.apply_upgrade(cards[0]); self.suppress_upgrade_advance=False; self.state="playing"; self.mode="arena"
                self.unlock_notice="ROGUE: "+cards[0][1]+" FOI SORTEADO"; self.unlock_notice_timer=3.0
            else:
                self.unlock_notice="ROGUE: PERSONAGEM SORTEADO"; self.unlock_notice_timer=3.0
        self.spawn_wave()

    def start_afk(self, character=None):
        chosen = character or self.selected_character
        self.__init__()
        self.selected_character = chosen
        self.state = "playing"
        self.mode = "afk"
        self.upgrade_return_mode = "afk"
        self.player = Player(self, chosen)
        self.player.pos = pygame.Vector2(W * 0.33, H * 0.52)
        self.wave = 1
        self.event_name = None
        self.spawn_training_dummy()
        self.damage_texts.append(DamageText("ZONA AFK", pygame.Vector2(self.player.pos), CYAN, 1.2))

    def mode_unlocked(self, key):
        if key in GAME_MODE_MAIN: return True
        if SAVE.get("cheat_all_chars",False): return True
        if key=="rogue": return int(SAVE.get("best_wave",0)) >= 40
        if key=="one_vs_all": return bool(SAVE.get("father_unlocked",False))
        if key=="glonk_hunt": return bool(SAVE.get("glonk_last_discovered",False))
        return False

    def mode_lock_text(self,key):
        if key=="rogue": return "ALCANCE WAVE 40"
        if key=="one_vs_all": return "DESBLOQUEIE O COLOSSO DO CAOS"
        if key=="glonk_hunt": return "DESCUBRA GLONK, O ULTIMO"
        return "BLOQUEADO"

    def open_mode_select(self):
        self.pending_game_mode=getattr(self,"game_mode","normal")
        self.state="mode_select"
        AUDIO.play("click",0.65)

    def mode_record(self,key):
        rec=SAVE.get("mode_records",{})
        return int(rec.get(key,0) or 0)

    def update_mode_record(self):
        if self.mode!="arena" or is_beta_character(self.player.character): return
        records=SAVE.setdefault("mode_records",{})
        value=self.kills if self.game_mode=="arena_survival" else self.wave
        records[self.game_mode]=max(int(records.get(self.game_mode,0) or 0),int(value))

    def open_character_select(self, target="arena"):
        self.selection_target = target
        self.character_tab = "characters"
        if self.selected_character in CHARACTER_ORDER:
            self.character_carousel_index = CHARACTER_ORDER.index(self.selected_character)
        self.character_swipe_start = None
        self.character_swipe_current = None
        self.character_swipe_finger = None
        self.state = "character_select"

    def open_difficulty_select(self, character):
        self.pending_character = character
        self.selected_character = character
        self.difficulty = "easy"
        self.state = "difficulty_select"
        AUDIO.play("click", 0.65)

    def character_unlocked(self, name):
        if SAVE.get("cheat_all_chars", False):
            return True
        if name == "Kayk":
            return SAVE.get("kayk_unlocked", False)
        if name == "Colosso do Caos":
            return SAVE.get("father_unlocked", False)
        if name == "Strikada Egoísta":
            return SAVE.get("strikada_unlocked", False)
        if name == HANK_KEY:
            return SAVE.get("hank_unlocked", False)
        if name == "Glonk 100% Power":
            return SAVE.get("glonk100_unlocked", False)
        if name == RIP_INDRA_KEY:
            normals=[a[0] for a in ACHIEVEMENTS if a[0]!="meta_all"]
            done=sum(1 for k in normals if k in set(SAVE.get("unlocked_achievements",[])))
            unlocked=done*2>=max(1,len(normals))
            if unlocked and not SAVE.get("rip_indra_unlocked",False):
                SAVE["rip_indra_unlocked"]=True; save_data(SAVE)
            return unlocked or SAVE.get("rip_indra_unlocked",False)
        if name == HISOKA_KEY:
            chars=set(SAVE.get("hisoka_impossible_wave30_chars",[]))
            unlocked=len(chars)>=3
            if unlocked and not SAVE.get("hisoka_unlocked",False): SAVE["hisoka_unlocked"]=True; save_data(SAVE)
            return unlocked or SAVE.get("hisoka_unlocked",False)
        if name in ("Sans", SUKUNA_KEY, "Potential Man"):
            return True
        return True

    def current_character_order(self):
        return BETA_CHARACTER_ORDER if self.character_tab == "beta" else CHARACTER_ORDER

    def selected_carousel_character(self):
        order=self.current_character_order()
        if not order:
            return "Ycaro"
        self.character_carousel_index %= len(order)
        return order[self.character_carousel_index]

    def spend_evolution_point(self, stat):
        if stat not in EVOLUTION_STAT_KEYS:
            return False
        char = self.selected_carousel_character()
        if is_beta_character(char):
            return False
        prof = evolution_profile(char)
        if prof.get("points", 0) <= 0 or prof.get(stat, 0) >= MAX_EVOLUTION_STAT:
            return False
        prof["points"] -= 1
        prof[stat] = prof.get(stat, 0) + 1
        save_data(SAVE)
        self.check_progress_achievements()
        AUDIO.play("upgrade", 0.65, 80)
        return True

    def roll_evolution_point(self):
        # V14: recompensa garantida por onda concluida em runs normais.
        if self.mode != "arena" or is_beta_character(self.player.character):
            return False
        prof = evolution_profile(self.player.character)
        if all(prof.get(k, 0) >= MAX_EVOLUTION_STAT for k in EVOLUTION_STAT_KEYS):
            return False
        prof["points"] = prof.get("points", 0) + 1
        prof["earned"] = prof.get("earned", 0) + 1
        save_data(SAVE)
        self.evolution_notice = f"+1 PONTO DE EVOLUCAO GARANTIDO PARA {self.player.character.upper()}!"
        self.evolution_notice_timer = 4.0
        return True

    def character_select_down(self, pos, finger_id=None):
        if self.state != "character_select":
            return
        self.character_swipe_start = pygame.Vector2(pos)
        self.character_swipe_current = pygame.Vector2(pos)
        self.character_swipe_finger = finger_id

    def character_select_motion(self, pos, finger_id=None):
        if self.state != "character_select" or self.character_swipe_start is None:
            return
        if self.character_swipe_finger is not None and finger_id != self.character_swipe_finger:
            return
        self.character_swipe_current = pygame.Vector2(pos)

    def character_select_up(self, pos, finger_id=None):
        if self.state != "character_select":
            return
        if self.character_swipe_start is None:
            self.click_ui(pos)
            return
        if self.character_swipe_finger is not None and finger_id != self.character_swipe_finger:
            return
        end = pygame.Vector2(pos)
        delta = end - self.character_swipe_start
        did_swipe = bool(self.current_character_order()) and abs(delta.x) >= S(110) and abs(delta.x) > abs(delta.y) * 1.15
        self.character_swipe_start = None
        self.character_swipe_current = None
        self.character_swipe_finger = None
        if did_swipe:
            step = -1 if delta.x < 0 else 1
            self.character_carousel_index = (self.character_carousel_index + step) % len(self.current_character_order())
            AUDIO.play("click", 0.45, 50)
        else:
            self.click_ui(pos)

    def start_bestiary_training(self, item):
        name=item.get("name","") if isinstance(item,dict) else str(item); chosen=self.selected_character if self.selected_character in CHARACTER_CONFIG else "Ycaro"
        self.__init__(); self.selected_character=chosen; self.state="playing"; self.mode="training"; self.upgrade_return_mode="training"; self.player=Player(self,chosen); self.player.pos=pygame.Vector2(W*0.30,H*0.52); self.wave=1; self.event_name=None; self.training_target_name=name; self.training_respawn_timer=1.5; self.spawn_bestiary_target(name); self.damage_texts.append(DamageText("TREINAMENTO: "+name,pygame.Vector2(self.player.pos),CYAN,1.2))

    def spawn_bestiary_target(self,name):
        pos=(W*0.68,H*0.48); e=None; normal={"PERSEGUIDOR":"chaser","ATIRADOR":"shooter","KITER":"kiter","TANQUE":"tank"}; elites={"ELITE: FRENESI":"frenzy","ELITE: GIGANTE":"giant","ELITE: BLINDADO":"armored","ELITE: EXPLOSIVO":"explosive"}; boss_waves={"COLOSSO DO CAOS":5,"O DEVORADOR":10,"A SENTINELA":15,"REI DO VAZIO":20}
        if name in ("Glonk","GLONK","Glonk, O Ultimo","GLONK, O ULTIMO"):
            # Unico treino que nasce com uma pequena horda: sem ela nao existiria a perseguicao/cutscene.
            extras=[]
            for i in range(7):
                ang=i*math.tau/7
                ep=pygame.Vector2(W*0.58,H*0.48)+vec_from_angle(ang)*S(230)
                ep.x=clamp(ep.x,S(80),W-S(80)); ep.y=clamp(ep.y,S(210),H-S(380))
                extras.append(Enemy(ep, random.choice(["chaser","shooter","kiter"]), 10, None))
            self.enemies.extend(extras)
            avg_hp=sum(x.max_hp for x in extras)/max(1,len(extras))
            avg_speed=sum(x.speed for x in extras)/max(1,len(extras))
            g=GlonkEnemy(pos,10,avg_hp*4.0,max(S(195),avg_speed*1.75),training=True)
            self.enemies.append(g)
            self.glonk_event_stage="spawn"; self.glonk_event_timer=2.0
            return True
        if name in normal: e=Enemy(pos,normal[name],10,None)
        elif name in elites: e=Enemy(pos,"chaser",20,elites[name])
        elif name in boss_waves: e=Boss(pos,boss_waves[name])
        elif name in ("A GULA","GULA"):
            cfg=next((x for x in SIN_SEQUENCE if x["key"]=="gula"),SIN_SEQUENCE[4]); e=SinBoss(pos,100,cfg,False)
        elif name=="ARCEBISPOS DOS PECADOS": e=SinBoss(pos,50,SIN_SEQUENCE[0],True)
        else:
            cfg=next((x for x in SIN_SEQUENCE if x["name"]==name),None)
            if cfg is not None: e=SinBoss(pos,100,cfg,False)
        if e is not None: self.enemies.append(e); return True
        return False

    def spawn_training_dummy(self):
        # Mantem no maximo 3 alvos para nao lotar a sala sem querer.
        dummies = [e for e in self.enemies if isinstance(e, TrainingDummy)]
        if len(dummies) >= 3:
            return
        slots = [(W * 0.67, H * 0.43), (W * 0.70, H * 0.57), (W * 0.55, H * 0.50)]
        self.enemies.append(TrainingDummy(slots[len(dummies)]))

    def spawn_afk_enemy(self):
        hostile = [e for e in self.enemies if not isinstance(e, TrainingDummy) and not isinstance(e, Boss)]
        if len(hostile) >= 16:
            return
        enemy = Enemy(self.random_spawn_pos(), random.choice(["chaser", "shooter", "kiter", "tank"]), max(3, self.wave))
        self.enemies.append(enemy)
        self.damage_texts.append(DamageText("INIMIGO DE TESTE", pygame.Vector2(enemy.pos), ORANGE, 0.8))

    def spawn_afk_boss(self):
        if sum(1 for e in self.enemies if isinstance(e, Boss) and not e.dead) >= 2:
            return
        boss = Boss((W*0.70, H*0.42), 5)
        boss.domain_cd = 1.0
        self.enemies.append(boss)
        self.damage_texts.append(DamageText("BOSS DE TESTE", pygame.Vector2(boss.pos), RED, 1.0))

    def afk_test_shot(self):
        # Cria um projetil inimigo vindo da frente para testar parry/dodge.
        p = self.player
        spawn = p.pos - p.facing * S(330)
        spawn.x = clamp(spawn.x, S(30), W-S(30))
        spawn.y = clamp(spawn.y, S(190), H-S(345))
        direction = p.pos - spawn
        if direction.length_squared() == 0:
            direction = pygame.Vector2(0, 1)
        direction = direction.normalize()
        self.projectiles.append(Projectile(spawn, direction * S(285), 10, "enemy", S(10), PINK, 3.0))

    def spawn_particles(self, pos, color, count):
        if getattr(self, "mass_hit_fx", False):
            count = min(count, 4)
        for _ in range(count):
            a = random.random() * math.tau
            sp = random.uniform(S(35), S(230))
            self.particles.append(Particle(pygame.Vector2(pos), vec_from_angle(a) * sp, color, random.uniform(0.25, 0.7), random.uniform(S(3), S(8))))

    def random_spawn_pos(self):
        side = random.randint(0, 3)
        margin = S(65)
        top = S(220)
        bottom = H - S(350)
        if side == 0:
            return pygame.Vector2(margin, random.randint(top, bottom))
        if side == 1:
            return pygame.Vector2(W - margin, random.randint(top, bottom))
        if side == 2:
            return pygame.Vector2(random.randint(margin, W-margin), top)
        return pygame.Vector2(random.randint(margin, W-margin), bottom)

    def forge_material_amount(self, key):
        if SAVE.get("cheat_items_infinite", False):
            return 9999
        mats = SAVE.get("forge_materials", {})
        return int(mats.get(key, 0)) if isinstance(mats, dict) else 0

    def collect_forge_material(self, key, amount=1):
        if key not in FORGE_MATERIALS or is_beta_character(self.player.character):
            return
        mats = SAVE.setdefault("forge_materials", {})
        mats[key] = int(mats.get(key,0)) + int(amount)
        disc = set(SAVE.get("forge_discovered", [])); disc.add(key); SAVE["forge_discovered"] = sorted(disc)
        save_data(SAVE)
        if key in SIN_FRAGMENTS and all(self.forge_material_amount(k)>=1 for k in SIN_FRAGMENTS):
            self.unlock_achievement("all_sin_fragments")
        info=FORGE_MATERIALS[key]; rarity=FORGE_RARITIES[info["rarity"]][0]
        self.damage_texts.append(DamageText(f"{rarity}: {info['name']}", pygame.Vector2(self.player.pos), FORGE_RARITIES[info["rarity"]][1], 1.1))
        AUDIO.play("pickup",0.7,80)

    def roll_forge_drop(self, enemy):
        if self.mode != "arena" or is_beta_character(self.player.character):
            return
        is_boss = isinstance(enemy, Boss)
        # Pecados entregam seu fragmento diretamente em SinBoss.die; aqui recebem apenas loot normal de boss.
        if is_boss:
            pool=["core","domain_crystal","boss_heart"]
            weights=[35,40,25]
            reward_mult = difficulty_cfg(getattr(self,"difficulty","easy"))["reward"] if self.mode=="arena" else 1.0
            if reward_mult >= 0.80: qty=random.randint(2,4)
            elif reward_mult >= 0.60: qty=random.randint(1,3)
            elif reward_mult >= 0.40: qty=random.randint(1,2)
            else: qty=1
            for i in range(qty):
                key=random.choices(pool,weights=weights,k=1)[0]
                self.drops.append(Drop(enemy.pos+pygame.Vector2(random.randint(-35,35),random.randint(-35,35)),"mat:"+key))
            return
        reward_mult = difficulty_cfg(getattr(self,"difficulty","easy"))["reward"] if self.mode=="arena" else 1.0
        chance = (0.035 + (0.045 if getattr(enemy,"elite",None) else 0.0) + min(0.04,self.wave*0.00008)) * reward_mult
        if random.random() > chance:
            return
        roll=random.random()
        if getattr(enemy,"elite",None) and roll < 0.22: key="core"
        elif roll < 0.18: key="essence"
        else: key="scrap"
        self.drops.append(Drop(enemy.pos,"mat:"+key))

    def can_craft_weapon(self, recipe):
        if recipe.get("preview",False):
            return False
        if SAVE.get("coins",0) < recipe["coins"]:
            return False
        return all(self.forge_material_amount(k) >= v for k,v in recipe["cost"].items())

    def craft_weapon(self, key):
        recipe=FORGE_WEAPON_BY_KEY.get(key)
        if not recipe:
            return False
        if recipe.get("preview",False):
            if recipe.get("testable",False):
                return self.equip_weapon(key)
            self.unlock_notice="ARMA BETA: PREVIA AINDA NAO FORJAVEL"; self.unlock_notice_timer=2.5
            return False
        crafted=set(SAVE.get("crafted_weapons", []))
        if key in crafted:
            return self.equip_weapon(key)
        if not self.can_craft_weapon(recipe):
            self.unlock_notice="MATERIAIS/MOEDAS INSUFICIENTES"; self.unlock_notice_timer=2.0; return False
        if not SAVE.get("cheat_items_infinite",False):
            SAVE["coins"] -= recipe["coins"]
            mats=SAVE.setdefault("forge_materials",{})
            for k,v in recipe["cost"].items(): mats[k]=max(0,int(mats.get(k,0))-v)
        crafted.add(key); SAVE["crafted_weapons"]=sorted(crafted)
        SAVE.setdefault("equipped_weapons",{})[recipe["character"]]=key
        save_data(SAVE); AUDIO.play("unlock",1.0)
        self.unlock_achievement("forge_first")
        if recipe.get("rarity")=="divine": self.unlock_achievement("divine_weapon")
        self.check_progress_achievements()
        self.unlock_notice=f"FORJADO: {recipe['name']}"; self.unlock_notice_timer=4.0
        return True

    def equip_weapon(self, key):
        recipe=FORGE_WEAPON_BY_KEY.get(key)
        if not recipe: return False
        beta_testable = bool(recipe.get("preview",False) and recipe.get("testable",False))
        if recipe.get("preview",False) and not beta_testable: return False
        if not beta_testable and key not in set(SAVE.get("crafted_weapons",[])): return False
        SAVE.setdefault("equipped_weapons",{})[recipe["character"]]=key
        save_data(SAVE); AUDIO.play("upgrade",0.75)
        self.unlock_notice=(f"BETA EQUIPADA: {recipe['name']}" if beta_testable else f"EQUIPADO: {recipe['name']}"); self.unlock_notice_timer=2.5
        return True

    def apply_difficulty_to_enemy(self, enemy):
        if self.mode != "arena" or getattr(enemy, "_difficulty_applied", False):
            return
        cfg = difficulty_cfg(getattr(self, "difficulty", "easy"))
        enemy.max_hp *= cfg["hp"]
        enemy.hp = enemy.max_hp
        enemy.speed *= cfg["speed"]
        enemy.contact_damage *= cfg["damage"]
        enemy.difficulty_force = cfg["force"]
        enemy.shoot_cd = max(0.05, getattr(enemy,"shoot_cd",0.5) / cfg["ai"])
        if isinstance(enemy, Boss):
            enemy.burst_cd = max(0.10, enemy.burst_cd / cfg["ai"])
            enemy.charge_cd = max(0.25, enemy.charge_cd / cfg["ai"])
            if enemy.domain_cd < 99999:
                enemy.domain_cd = max(1.2, enemy.domain_cd / cfg["ai"])
        enemy._difficulty_applied = True

    def choose_event(self):
        self.event_name = None
        self.enemy_speed_mult = 1.0
        self.coin_multiplier = 1.0
        self.enemy_damage_mult = 1.0
        self.player_event_damage_mult = 1.0
        if self.wave >= 3 and self.wave % 3 == 0:
            roll = random.choice(["FRENESI", "CHUVA DE OURO", "VIDRO"])
            self.event_name = roll
            if roll == "FRENESI":
                self.enemy_speed_mult = 1.25
                self.coin_multiplier = 2.0
            elif roll == "CHUVA DE OURO":
                self.coin_multiplier = 2.5
            elif roll == "VIDRO":
                self.player_event_damage_mult = 1.25
                self.enemy_damage_mult = 1.25
                self.coin_multiplier = 1.5

    def apply_infinite_curses_to_spawn(self):
        hp_mult=1.20**self.infinite_curses.count("enemy_hp")
        dmg_mult=1.15**self.infinite_curses.count("enemy_damage")
        boss_mult=1.30**self.infinite_curses.count("boss_hp")
        for e in self.enemies:
            if hp_mult!=1.0:
                e.max_hp*=hp_mult; e.hp*=hp_mult
            e.contact_damage*=dmg_mult
            if isinstance(e,Boss) and boss_mult!=1.0:
                e.max_hp*=boss_mult; e.hp*=boss_mult
                if hasattr(e,"boss_damage_scale"): e.boss_damage_scale*=dmg_mult

    def open_curse_choice(self):
        pool=list(INFINITE_CURSES)
        random.shuffle(pool)
        self.curse_choice_cards=pool[:2]
        self.curse_choice_rects=[]
        self.state="curse_choice"
        AUDIO.play("boss",0.65,150)

    def choose_infinite_curse(self,key):
        self.infinite_curses.append(key)
        if key=="stamina": self.player.stamina_regen*=0.80
        self.damage_texts.append(DamageText("MALDICAO: "+next((x[1] for x in INFINITE_CURSES if x[0]==key),key),pygame.Vector2(self.player.pos),PURPLE,1.1))
        self.state="playing"
        self.open_upgrade()

    def add_evolution_trait(self):
        key,name,desc=random.choice(EVOLUTION_TRAITS)
        self.evolution_traits.append(key)
        self.unlock_notice=f"INIMIGOS EVOLUIRAM: {name}"; self.unlock_notice_timer=3.0

    def apply_evolution_traits_to_spawn(self):
        hp=1.12**self.evolution_traits.count("carapace")
        dmg=1.10**self.evolution_traits.count("claws")
        spd=min(1.35,1.03**self.evolution_traits.count("instinct"))
        mind=0.90**self.evolution_traits.count("mind")
        for e in self.enemies:
            e.max_hp*=hp; e.hp*=hp; e.contact_damage*=dmg; e.speed*=spd
            if hasattr(e,"shoot_cd"): e.shoot_cd=max(0.05,e.shoot_cd*mind)
            if isinstance(e,Boss):
                e.burst_cd=max(0.08,e.burst_cd*mind); e.charge_cd=max(0.18,e.charge_cd*mind)

    def apply_rogue_rule_to_spawn(self):
        if not self.rogue_rule: return
        key=self.rogue_rule
        for e in self.enemies:
            if key=="frenzy":
                if hasattr(e,"shoot_cd"): e.shoot_cd*=0.65
                if isinstance(e,Boss): e.burst_cd*=0.65; e.charge_cd*=0.72
            elif key=="thick": e.max_hp*=1.35; e.hp*=1.35
            elif key=="glass": e.contact_damage*=1.35
            elif key=="elite" and isinstance(e,Enemy) and not isinstance(e,Boss) and not e.elite: e.elite=random.choice(["frenzy","giant","armored","explosive"])

    def boss_rush_sequence_length(self):
        return 4+len(SIN_SEQUENCE)+(1 if SAVE.get("glonk_last_discovered",False) else 0)

    def spawn_boss_rush_wave(self):
        idx=self.wave-1
        total=self.boss_rush_sequence_length()
        if idx>=total:
            self.complete_mode("BOSS RUSH COMPLETO",f"{total} bosses derrotados")
            return
        if idx<4:
            fake_wave=(idx+1)*5
            b=Boss((W/2,S(350)),fake_wave)
        elif idx<4+len(SIN_SEQUENCE):
            cfg=SIN_SEQUENCE[idx-4]
            b=SinBoss((W/2,S(350)),max(40,(idx+1)*10),cfg,False)
        else:
            b=GlonkEnemy((W/2,S(350)),self.wave,1800+450*self.wave,S(250),False)
            b.finish_transform(self)
        # Herancas acumuladas tornam cada boss um pouco mais monstruoso.
        stacks=len(self.boss_heritages)
        if stacks:
            b.max_hp*=1.0+0.10*stacks; b.hp=b.max_hp; b.speed*=min(1.25,1.0+0.025*stacks)
            b.contact_damage*=1.0+0.07*stacks
            if isinstance(b,Boss): b.burst_cd=max(0.15,b.burst_cd*(0.95**stacks)); b.charge_cd=max(0.35,b.charge_cd*(0.96**stacks))
        self.enemies=[b]
        self.apply_difficulty_to_enemy(b)
        self.wave_banner=1.7; self.wave_clear_lock=False
        AUDIO.play("boss",0.95,300)

    def spawn_one_vs_all_wave(self):
        idx=self.wave-1
        if idx>=len(self.one_vs_all_roster):
            self.unlock_achievement("solo_survivor") if any(a[0]=="solo_survivor" for a in ACHIEVEMENTS) else None
            self.complete_mode("SOBROU SO VOCE",f"{len(self.one_vs_all_roster)} rivais derrotados")
            return
        c=self.one_vs_all_roster[idx]
        r=CharacterRival((W/2,S(350)),self.wave,c)
        self.enemies=[r]; self.apply_difficulty_to_enemy(r); self.wave_banner=1.7; self.wave_clear_lock=False
        self.unlock_notice=f"RIVAL: {c.upper()}"; self.unlock_notice_timer=2.0

    def spawn_arena_pack(self, amount=5):
        for _ in range(max(1,amount)):
            kind=random.choice(["chaser","shooter","kiter","tank"] if self.wave>=3 else ["chaser","shooter"])
            elite=random.choice([None,None,None,"frenzy","armored","explosive"]) if self.wave>=3 else None
            e=Enemy(self.random_spawn_pos(),kind,max(1,self.wave),elite)
            e.speed*=self.enemy_speed_mult*self.enemy_perma_speed_mult; e.contact_damage*=self.enemy_damage_mult
            self.enemies.append(e); self.apply_difficulty_to_enemy(e)

    def update_arena_survival(self,dt):
        self.wave=max(1,1+int(self.time//25.0))
        self.arena_inset=min(S(190),int(self.time//45.0)*S(28))
        # A arena literalmente fecha: ficar fora do retangulo seguro causa dano constante.
        if self.arena_inset>0:
            left=self.arena_inset; right=W-self.arena_inset; top=S(175)+self.arena_inset*0.35; bottom=H-S(345)-self.arena_inset*0.35
            if not (left<=self.player.pos.x<=right and top<=self.player.pos.y<=bottom):
                self.player.take_damage(self.player.max_hp*0.018*dt,self)
        self.arena_spawn_timer-=dt; self.arena_hazard_timer-=dt
        target=min(34,5+int(self.time//18)*2)
        if self.arena_spawn_timer<=0 and len(self.enemies)<target:
            self.spawn_arena_pack(min(3,target-len(self.enemies)))
            self.arena_spawn_timer=max(0.35,1.25-self.time*0.002)
        if self.kills>=self.arena_next_reward and not self.arena_reward_cards:
            self.arena_reward_cards=self.generate_upgrades(3); self.arena_next_reward+=15
            self.unlock_notice="ESCOLHA SUA RECOMPENSA - O JOGO NAO PAUSA"; self.unlock_notice_timer=2.0
        if self.arena_hazard_timer<=0:
            self.arena_hazard_timer=max(5.5,10.0-self.time/100.0)
            self.arena_hazards.append({"pos":pygame.Vector2(random.uniform(S(150),W-S(150)),random.uniform(S(260),H-S(420))),"r":S(random.randint(95,165)),"t":2.2,"boom":False})
        alive=[]
        for h in self.arena_hazards:
            h["t"]-=dt
            if h["t"]<=0 and not h["boom"]:
                h["boom"]=True; h["t"]=0.55
                if self.player.pos.distance_to(h["pos"])<=h["r"]+self.player.radius:
                    self.player.take_damage(self.player.max_hp*0.12,self)
                old=self.current_damage_kind; self.current_damage_kind="arena_hazard"
                for e in self.enemies:
                    if not e.dead and e.pos.distance_to(h["pos"])<=h["r"]+e.radius: e.damage(e.max_hp*0.16,self,h["pos"],minimal_fx=True)
                self.current_damage_kind=old; self.shake=max(self.shake,S(10))
            if h["t"]>0: alive.append(h)
        self.arena_hazards=alive

    def pick_arena_reward(self,card):
        if not card: return
        self.suppress_upgrade_advance=True
        self.apply_upgrade(card)
        self.suppress_upgrade_advance=False
        self.arena_reward_cards=[]; self.arena_reward_rects=[]; self.state="playing"; self.mode="arena"

    def complete_mode(self,title,subtitle):
        self.bank_run_rewards(); self.mode_complete_title=title; self.mode_complete_subtitle=subtitle; self.state="mode_complete"
        AUDIO.play("unlock",1.0,100)

    def spawn_wave(self):
        if getattr(self.player,"glonk_101_power",False): self.player.glonk_101_ready=True
        if self.player.character=="Glonk" and getattr(self.player,"glonk_not_supposed",False):
            self.player.shield=max(self.player.shield,1)
        self.update_mission_wave()
        self.wave_clear_lock=False
        if hasattr(self.player, "vasco_wave_start"):
            self.player.vasco_wave_start()
        # Modos com estrutura de spawn propria.
        if self.game_mode=="boss_rush":
            self.spawn_boss_rush_wave(); return
        if self.game_mode=="one_vs_all":
            self.spawn_one_vs_all_wave(); return
        if self.game_mode=="arena_survival":
            self.enemies=[]; self.spawn_arena_pack(6); self.wave_banner=1.2; return
        # ROGUE sorteia uma regra nova em TODA wave.
        if self.game_mode=="rogue":
            self.rogue_rule=random.choice(ROGUE_RULES)[0]
            label=next(x[1] for x in ROGUE_RULES if x[0]==self.rogue_rule)
            self.unlock_notice="REGRA ROGUE: "+label; self.unlock_notice_timer=2.2
        self.wave_banner = 1.7
        self.wave_clear_lock = False
        self.choose_event()
        # V14 FINAL: a primeira onda de uma run baseada em waves NUNCA e boss,
        # independente da dificuldade. Boss Rush/Um Contra Todos mantem estrutura propria.
        special_sin = None if self.wave == 1 else sin_encounter_for_wave(self.wave)
        if self.game_mode=="rogue" and special_sin is not None:
            special_sin=(random.choice(SIN_SEQUENCE), random.choice([True,False]))
        if special_sin is not None:
            sin_cfg, is_archbishop = special_sin
            boss = SinBoss((W/2,S(350)),self.wave,sin_cfg,is_archbishop)
            if sin_cfg["key"] == "gula" and not is_archbishop:
                self.unlock_notice = f"A GULA LEMBRA DE VOCE | FOME {SAVE.get('gula_hunger',0)}"
                self.unlock_notice_timer = 7.0
            boss.speed *= self.enemy_speed_mult * self.enemy_perma_speed_mult
            boss.contact_damage *= self.enemy_damage_mult
            self.enemies.append(boss)
            AUDIO.play("boss",0.95,500)
        elif self.wave > 1 and self.wave % 5 == 0:
            boss = Boss((W/2, S(350)), self.wave)
            if self.game_mode=="rogue":
                rcfg=random.choice(BOSS_VARIANTS); boss.variant=rcfg["key"]; boss.name=rcfg["name"]; boss.color=rcfg["color"]; boss.domain_name=rcfg["domain"]; boss.domain_desc=rcfg["domain_desc"]
            boss.speed *= self.enemy_speed_mult * self.enemy_perma_speed_mult
            boss.contact_damage *= self.enemy_damage_mult
            self.enemies.append(boss)
            AUDIO.play("boss", 0.95, 500)
            dcfg = difficulty_cfg(getattr(self,"difficulty","easy"))
            cw = effective_combat_wave(self.wave)
            base_adds = min(6 if cw >= 100 else 3, max(1, cw // 80 + 2))
            adds = max(1, int(math.ceil(base_adds * dcfg["count"])))
            for _ in range(adds):
                e = Enemy(self.random_spawn_pos(), random.choice(["chaser", "shooter", "kiter", "tank"]), self.wave,
                          random.choice([None, "frenzy", "giant", "armored", "explosive"]) if self.wave >= 100 else None)
                e.speed *= self.enemy_speed_mult * self.enemy_perma_speed_mult
                e.contact_damage *= self.enemy_damage_mult
                self.enemies.append(e)
        else:
            dcfg = difficulty_cfg(getattr(self,"difficulty","easy"))
            cw = effective_combat_wave(self.wave)
            count_cap = int((36 if cw >= 150 else (32 if cw >= 75 else 28)) * dcfg["count"])
            mode_count_mult=1.0
            if self.game_mode=="infinite": mode_count_mult*=1.20**self.infinite_curses.count("horde")
            if self.game_mode=="evolution": mode_count_mult*=1.05**self.evolution_traits.count("mutation")
            if self.game_mode=="rogue" and self.rogue_rule=="swarm": mode_count_mult*=1.45
            count = min(max(1,int((4 + cw * 2) * dcfg["count"] * mode_count_mult)), max(count_cap,int(count_cap*mode_count_mult)))
            kinds = ["chaser", "shooter"]
            if cw >= 2:
                kinds.append("kiter")
            if cw >= 3:
                kinds.append("tank")
            elite_cap = min(0.94, (0.72 if cw >= 150 else 0.52 if cw >= 75 else 0.37) + dcfg["elite"])
            elite_bonus=0.0
            if self.game_mode=="infinite": elite_bonus+=0.12*self.infinite_curses.count("elite")
            if self.game_mode=="evolution": elite_bonus+=0.05*self.evolution_traits.count("mutation")
            if self.game_mode=="rogue" and self.rogue_rule=="elite": elite_bonus+=0.55
            elite_chance = min(0.98, min(0.08 + cw * 0.015 + dcfg["elite"] + elite_bonus, elite_cap+elite_bonus))
            for _ in range(count):
                kind = random.choice(kinds)
                elite = None
                if random.random() < elite_chance:
                    elite = random.choice(["frenzy", "giant", "armored", "explosive"])
                e = Enemy(self.random_spawn_pos(), kind, self.wave, elite)
                e.speed *= self.enemy_speed_mult * self.enemy_perma_speed_mult
                e.contact_damage *= self.enemy_damage_mult
                self.enemies.append(e)

        # Aplica o preset por ultimo.
        for enemy in self.enemies:
            self.apply_difficulty_to_enemy(enemy)
        if self.game_mode=="infinite": self.apply_infinite_curses_to_spawn()
        if self.game_mode=="evolution": self.apply_evolution_traits_to_spawn()
        if self.game_mode=="rogue": self.apply_rogue_rule_to_spawn()

        # CACA AO GLONK: toda wave obrigatoriamente possui Glonk; a IA escala com a wave.
        if self.game_mode=="glonk_hunt":
            self.spawn_rare_glonk()
            glonks=[e for e in self.enemies if isinstance(e,GlonkEnemy)]
            for g in glonks:
                g.speed*=min(1.45,1.0+0.035*max(0,self.wave-1)); g.hunt_level=self.wave
            # A partir da wave 5 surgem copias convincentes. Qualquer uma pode ser o ultimo.
            if self.wave>=5:
                for _ in range(min(2,1+(self.wave>=9))):
                    probe=next((g for g in glonks),None)
                    hp=(probe.max_hp*0.55 if probe else 300)
                    fake=GlonkEnemy(self.random_spawn_pos(),self.wave,hp,S(215),False); fake.is_decoy=True; fake.hunt_level=self.wave; fake._difficulty_applied=True
                    self.enemies.append(fake)

        # 5% por wave: um inimigo comum e SUBSTITUIDO pelo Glonk raro.
        # Em waves compostas apenas por boss/pecado, ele entra como a "vaga" rara extra,
        # para a chance continuar existindo literalmente em qualquer onda.
        glonk_chance=0.10 if (self.game_mode=="rogue" and self.rogue_rule=="glonk") else 0.05
        if self.mode == "arena" and self.game_mode!="glonk_hunt" and random.random() < glonk_chance:
            self.spawn_rare_glonk()

    def spawn_rare_glonk(self):
        regular=[e for e in self.enemies if not getattr(e,"dead",False) and isinstance(e,Enemy) and not isinstance(e,Boss) and not isinstance(e,GlonkEnemy)]
        if regular:
            victim=random.choice(regular)
            pos=pygame.Vector2(victim.pos)
            hp_pool=[e.max_hp for e in regular]
            speed_pool=[e.speed for e in regular]
            # substituicao real: o inimigo escolhido simplesmente deixa de existir, sem recompensa/kill.
            self.enemies.remove(victim)
        else:
            pos=pygame.Vector2(self.random_spawn_pos())
            # Referencia de um inimigo comum da wave, sem adicionar o objeto a arena.
            probe=Enemy(pos,"chaser",self.wave,None)
            cfg=difficulty_cfg(getattr(self,"difficulty","easy"))
            hp_pool=[probe.max_hp*cfg["hp"]]
            speed_pool=[probe.speed*cfg["speed"]]
        avg_hp=sum(hp_pool)/max(1,len(hp_pool))
        avg_speed=sum(speed_pool)/max(1,len(speed_pool))
        flee_speed=min(S(290),max(S(195),avg_speed*1.75))
        glonk=GlonkEnemy(pos,self.wave,avg_hp*4.0,flee_speed,training=False)
        glonk._difficulty_applied=True
        self.enemies.append(glonk)
        self.glonk_event_stage="spawn"
        self.glonk_event_timer=2.4
        AUDIO.play("glonk",0.95,100)
        self.damage_texts.append(DamageText("Um Glonk apareceu.",pygame.Vector2(glonk.pos),GREEN,1.5))

    def gula_devour(self, source=None):
        """Golpe especial da Gula: respeita dash/invulnerabilidade/escudo, mas se entrar, encerra a run."""
        if self.state != "playing" or self.mode != "arena":
            return False
        p = self.player
        if p.invuln > 0 or p.dash_time > 0:
            return False
        if p.shield > 0:
            p.shield -= 1
            p.invuln = 0.35
            AUDIO.play("shield", 0.9, 60)
            self.damage_texts.append(DamageText("A GULA BATEU NO ESCUDO!", pygame.Vector2(p.pos), BLUE, 0.9))
            return False
        self.devoured_by_gula = True
        if not is_beta_character(p.character):
            SAVE["gula_hunger"] = SAVE.get("gula_hunger", 0) + 1
            self.gula_death_hunger = SAVE["gula_hunger"]
            save_data(SAVE)
        else:
            self.gula_death_hunger = SAVE.get("gula_hunger", 0)
        p.hp = 0
        self.end_run()
        return True

    def bank_run_rewards(self):
        """Salva uma unica vez as recompensas acumuladas numa run normal.

        Materiais da Forja ja sao persistidos no momento do pickup; aqui liquidamos
        principalmente as moedas da run e os recordes. Beta/treino/AFK continuam sandbox.
        """
        if self.run_rewards_banked or self.mode != "arena" or is_beta_character(self.player.character):
            return False
        SAVE["coins"] += int(self.run_coins)
        SAVE["best_wave"] = max(int(SAVE.get("best_wave", 0)), int(self.wave))
        SAVE["best_kills"] = max(int(SAVE.get("best_kills", 0)), int(self.kills))
        self.update_mode_record()
        self.run_rewards_banked = True
        save_data(SAVE)
        return True

    def leave_run_to_menu(self):
        """Saida voluntaria: guarda o que foi conquistado antes de abandonar a run."""
        self.bank_run_rewards()
        self.attack_held = False; self.parry_held=False; self.domain_held=False; self.dash_held=False; self.aim_active=False; self.aim_finger=None; self.aim_mouse_active=False
        for key in self.move_touch:
            self.move_touch[key] = False
        self.active_fingers.clear()
        self.joystick_finger = None
        self.joystick_mouse_active = False
        self.joystick_vector.update(0, 0)
        self.state = "menu"

    def end_run(self):
        if self.player.character == "Glonk":
            # Treino/AFK nao contam. Em runs reais, cada morte aproxima o unlock do Glonk 100% Power.
            if self.mode == "arena":
                SAVE["glonk_deaths"] = int(SAVE.get("glonk_deaths", 0)) + 1
                if SAVE["glonk_deaths"] >= 100 and not SAVE.get("glonk100_unlocked", False):
                    SAVE["glonk100_unlocked"] = True
                    self.unlock_notice = "GLONK 100% POWER DESBLOQUEADO!"
                    self.unlock_notice_timer = 6.0
                    AUDIO.play("unlock", 1.0)
                save_data(SAVE)
            self.bank_run_rewards()
            AUDIO.play("glonk", 1.0)
            self.state = "glonk_death"
            self.attack_held = False; self.parry_held=False; self.domain_held=False; self.dash_held=False; self.aim_active=False; self.aim_finger=None; self.aim_mouse_active=False
            for key in self.move_touch:
                self.move_touch[key] = False
            return
        if self.mode in ("afk", "training"):
            # Laboratorio/treino: nao existe Game Over. Ao morrer, HP e estamina voltam cheios.
            self.player.hp = self.player.max_hp
            self.player.stamina = self.player.max_stamina
            self.player.invuln = 1.0
            self.healing_locked = False
            self.damage_texts.append(DamageText("RESET HP", pygame.Vector2(self.player.pos), GREEN))
            return
        if self.state == "death":
            return
        AUDIO.play("death", 0.95)
        self.state = "death"
        elapsed = max(1, (pygame.time.get_ticks() - self.start_ticks) // 1000)
        self.final_time = elapsed
        self.bank_run_rewards()

    def get_enemy_target(self, pos):
        """Escolhe alvo entre jogador, amigos do Ruan e shikigamis do Potential Man."""
        alive = [serv for serv in self.servants if not serv.dead]
        alive += [x for x in self.potential_summons if not getattr(x,"dead",True)]
        alive += [x for x in self.vinicius_turrets if not getattr(x,"dead",True)]
        alive += [x for x in self.vinicius_walls if not getattr(x,"dead",True)]
        taunts=[x for x in alive if getattr(x,"taunt",False)]
        if taunts:
            origin=pygame.Vector2(pos); near=min(taunts,key=lambda ent:origin.distance_to(ent.pos))
            if origin.distance_to(near.pos)<=S(720): return near
        if not alive:
            return self.player
        origin=pygame.Vector2(pos)
        player_dist=origin.distance_to(self.player.pos)
        nearest=min(alive,key=lambda ent: origin.distance_to(ent.pos))
        entity_dist=origin.distance_to(nearest.pos)
        if getattr(nearest,"guardian",False) or entity_dist < player_dist*1.12 or entity_dist<=S(330):
            return nearest
        return self.player

    def check_beta_character_unlock_quests(self):
        # Hisoka: wave 30 no Impossivel com 3 personagens diferentes fora do sexteto principal.
        if self.mode!="arena" or getattr(self,"difficulty","easy")!="impossible" or self.wave<30:
            return
        core={"Ycaro","Ana","Kayk","Kevyn","Pedro","Ruan"}
        char=self.player.character
        # BETA = sandbox absoluto: nunca conta para quest, unlock, conquista ou recompensa persistente.
        if is_beta_character(char) or char in core:
            return
        chars=list(dict.fromkeys(SAVE.get("hisoka_impossible_wave30_chars",[])))
        if char not in chars:
            chars.append(char); SAVE["hisoka_impossible_wave30_chars"]=chars
            if len(chars)>=3: SAVE["hisoka_unlocked"]=True; self.unlock_notice="HISOKA MORROW DESBLOQUEADO!"
            else: self.unlock_notice=f"QUEST HISOKA: {len(chars)}/3 PERSONAGENS"
            self.unlock_notice_timer=2.5; save_data(SAVE)

    def player_in_boss_domain(self, variant=None):
        for e in self.enemies:
            if isinstance(e, Boss) and not e.dead and e.domain_active and e.is_in_domain(self.player.pos):
                if variant is None or e.variant == variant:
                    return True
        return False

    def domains_overlap(self, boss):
        if self.player.character in ("Sans", "Potential Man"):
            return False
        if not self.domain_active or not boss.domain_active:
            return False
        return self.domain_center.distance_to(boss.domain_center) <= self.domain_radius + boss.domain_radius

    def start_domain_clash(self, boss):
        if self.domain_clash_active or not self.domain_active or not boss.domain_active:
            return
        self.domain_clash_active = True
        self.domain_clash_timer = 5.0
        self.domain_clash_score = -10.0
        self.domain_clash_boss = boss
        # Garante que nenhum dos dois dominios expire no meio do Clash.
        self.domain_timer = max(self.domain_timer, 5.25)
        boss.domain_timer = max(boss.domain_timer, 5.25)
        self.clash_result = "CLASH DE DOMINIO"
        self.clash_result_timer = 1.8
        AUDIO.play("domain", 1.0, 250)
        self.shake = max(self.shake, S(16))

    def record_clash_damage(self, amount):
        if self.domain_clash_active:
            # Dano precisa sustentar o Clash; ataques fortes empurram a barra mais.
            self.domain_clash_score += max(0.5, amount * 0.22)
            self.domain_clash_score = min(120.0, self.domain_clash_score)

    def record_clash_hurt(self, amount):
        if self.domain_clash_active:
            self.domain_clash_score -= max(0.5, amount * 0.34)

    def record_clash_parry(self):
        if self.domain_clash_active:
            self.domain_clash_score += 5.0

    def update_bad_time(self, dt):
        if not self.bad_time_active or self.player.character != "Sans":
            return
        self.bad_time_bone_cd -= dt
        self.bad_time_obstacle_cd -= dt
        # Rajadas automaticas de ossos no alvo mais proximo.
        if self.bad_time_bone_cd <= 0:
            targets=[e for e in self.enemies if not e.dead]
            if targets:
                target=min(targets,key=lambda e:e.pos.distance_to(self.player.pos))
                d=target.pos-self.player.pos
                if d.length_squared()>0:
                    d=d.normalize()
                    pr=Projectile(self.player.pos+d*S(35),d*S(900),self.player.base_damage*0.62,"player",S(8),WHITE,1.9,self.player.projectile_pierce)
                    pr.kind="sans_bad_time_bone"; pr.origin=pygame.Vector2(self.player.pos)
                    self.projectiles.append(pr)
            self.bad_time_bone_cd=0.20 if self.player.sans_worse_time else 0.30
        if self.bad_time_obstacle_cd <= 0 and len(self.sans_bones) < 9:
            px=random.uniform(S(120),W-S(120)); py=random.uniform(S(230),H-S(390))
            self.sans_bones.append(SansBoneObstacle((px,py),self.player.base_damage*0.52))
            self.bad_time_obstacle_cd=random.uniform(0.55,0.85)
        # Durante BAD TIME o Blaster mira sozinho e recarrega em 2 segundos.
        if self.player.sans_blaster_cd <= 0:
            self.player.fire_sans_blaster(self,auto=True)

    def update_domain_clash(self, dt):
        if not self.domain_clash_active:
            return
        boss = self.domain_clash_boss
        if boss is None:
            self.domain_clash_active = False
            return
        if boss.dead:
            self.domain_clash_active = False
            self.domain_timer += 3.0
            self.clash_result = "DOMINIO SOBERANO! +3s"
            self.clash_result_timer = 2.4
            AUDIO.play("synergy", 1.0)
            self.record_clash_win()
            return
        if not self.domain_active or not boss.domain_active:
            self.domain_clash_active = False
            return
        # Se os circulos se separarem, o Clash ainda continua: os Dominios ja se enfrentaram.
        # A barra perde poder o tempo inteiro. Nao basta causar dano no inicio e fugir ate acabar.
        self.domain_clash_score = max(-120.0, self.domain_clash_score - 4.0 * dt)
        self.domain_clash_timer -= dt
        if self.domain_clash_timer > 0:
            return
        self.domain_clash_active = False
        if self.domain_clash_score >= 0:
            boss.domain_active = False
            boss.domain_timer = 0
            self.domain_timer += 3.0
            self.clash_result = "DOMINIO SOBERANO! +3s"
            self.clash_result_timer = 2.4
            AUDIO.play("synergy", 1.0)
            self.record_clash_win()
        else:
            self.domain_active = False
            self.domain_timer = 0
            if self.player.character==LIRA_KEY: self.player.lira_end_domain(self)
            if self.ruan_guardian is not None:
                self.ruan_guardian.dead = True
                self.ruan_guardian = None
            boss.domain_timer += 3.0
            boss.clash_buff_timer = 5.0
            self.clash_result = "DOMINIO QUEBRADO! BOSS FORTALECIDO"
            self.clash_result_timer = 2.4
            AUDIO.play("hurt", 0.9)

    def record_clash_win(self):
        if self.mode != "arena" or is_beta_character(self.player.character):
            return
        SAVE["clash_wins"] = SAVE.get("clash_wins", 0) + 1
        save_data(SAVE)
        self.check_progress_achievements()

    def _achievement_metric(self, metric):
        if metric=="kills": return int(SAVE.get("total_kills",0))
        if metric=="wave": return int(SAVE.get("best_wave",0))
        if metric=="domains": return int(SAVE.get("total_domains",0))
        if metric=="clashes": return int(SAVE.get("clash_wins",0))
        if metric=="crafted": return len(set(SAVE.get("crafted_weapons",[])))
        if metric=="missions": return len(set(SAVE.get("completed_missions",[])))
        if metric=="evo_spent":
            total=0
            root=SAVE.get("character_evolution",{})
            if isinstance(root,dict):
                for char,prof in root.items():
                    if is_beta_character(char) or not isinstance(prof,dict): continue
                    total += sum(max(0,int(prof.get(k,0))) for k in EVOLUTION_STAT_KEYS)
            return total
        if metric=="max_level":
            vals=[evolution_level(c) for c in CHARACTER_ORDER if not is_beta_character(c)]
            return max(vals) if vals else 1
        if metric.startswith("sin_defeat:"):
            return 1 if metric.split(":",1)[1] in set(SAVE.get("sin_defeats",[])) else 0
        if metric=="sins_defeated": return len(set(SAVE.get("sin_defeats",[])))
        if metric.startswith("fragment:"):
            return self.forge_material_amount(metric.split(":",1)[1])
        if metric=="fragments_all": return sum(1 for k in SIN_FRAGMENTS if self.forge_material_amount(k)>=1)
        if metric=="run_parries": return int(getattr(self,"parries",0))
        if metric=="run_dodges": return int(getattr(self,"perfect_dodges",0))
        if metric=="run_combo": return int(getattr(self,"combo",0))
        if metric=="pineapple_refunds": return int(SAVE.get("pineapple_refunds",0))
        if metric=="run_friends": return sum(1 for x in getattr(self,"servants",[]) if not x.dead and not x.guardian)
        if metric=="father_unlock": return 1 if SAVE.get("father_unlocked",False) else 0
        if metric=="divine_weapon":
            return 1 if any(FORGE_WEAPON_BY_KEY.get(k,{}).get("rarity")=="divine" for k in SAVE.get("crafted_weapons",[])) else 0
        return 0

    def achievement_progress(self,key):
        if key=="meta_all":
            unlocked=set(SAVE.get("unlocked_achievements",[])); normals=[a[0] for a in ACHIEVEMENTS if a[0]!="meta_all"]
            cur=sum(1 for k in normals if k in unlocked); goal=len(normals)
            return cur,goal,(100.0*cur/max(1,goal))
        rule=ACHIEVEMENT_PROGRESS_RULES.get(key)
        if not rule:
            return (1,1,100.0) if key in set(SAVE.get("unlocked_achievements",[])) else (0,1,0.0)
        metric,goal=rule; cur=self._achievement_metric(metric)
        return cur,goal,100.0*min(cur,goal)/max(1,goal)

    def check_progress_achievements(self):
        if hasattr(self,"player") and is_beta_character(getattr(self.player,"character","")) and self.mode=="arena": return
        for key,(metric,goal) in ACHIEVEMENT_PROGRESS_RULES.items():
            if self._achievement_metric(metric)>=goal:
                self.unlock_achievement(key)

    def unlock_achievement(self, key):
        # Beta, Zona AFK e Treinamento sao sandbox e nao liberam progresso persistente.
        if self.mode != "arena":
            return False
        if hasattr(self, "player") and is_beta_character(getattr(self.player, "character", "")):
            return False
        unlocked = set(SAVE.get("unlocked_achievements", []))
        if key in unlocked:
            return False
        entry = next((a for a in ACHIEVEMENTS if a[0] == key), None)
        if entry is None:
            return False
        unlocked.add(key)
        SAVE["unlocked_achievements"] = sorted(unlocked)
        # A ultima conquista nasce automaticamente quando TODAS as outras foram concluidas.
        meta_new=False
        if key != "meta_all":
            normal_keys={a[0] for a in ACHIEVEMENTS if a[0] != "meta_all"}
            if normal_keys.issubset(unlocked) and "meta_all" not in unlocked:
                unlocked.add("meta_all"); meta_new=True
                SAVE["unlocked_achievements"] = sorted(unlocked)
        save_data(SAVE)
        self.achievement = "Não é difícil, só e chato" if meta_new else entry[1]
        self.achievement_timer = 3.2
        AUDIO.play("unlock", 0.9)
        return True

    def sync_saved_achievements(self):
        """Reconcilia as 100 conquistas com progresso persistente de saves antigos."""
        unlocked=set(SAVE.get("unlocked_achievements",[]))
        for key,(metric,goal) in ACHIEVEMENT_PROGRESS_RULES.items():
            if self._achievement_metric(metric)>=goal:
                unlocked.add(key)
        normal_keys={a[0] for a in ACHIEVEMENTS if a[0]!="meta_all"}
        if normal_keys.issubset(unlocked): unlocked.add("meta_all")
        SAVE["unlocked_achievements"]=sorted(unlocked); save_data(SAVE)

    def mission_stats_for(self, character):
        all_stats = SAVE.setdefault("mission_stats", {})
        stats = all_stats.setdefault(character, {"kills": 0, "domains": 0, "best_wave": 0, "runs": 0})
        for key in ("kills", "domains", "best_wave", "runs"):
            stats.setdefault(key, 0)
        return stats

    def check_character_missions(self, character):
        stats = self.mission_stats_for(character)
        completed = set(SAVE.get("completed_missions", []))
        changed = False
        for mission_id, name, desc, stat_key, goal, reward in CHARACTER_MISSIONS.get(character, []):
            if mission_id not in completed and stats.get(stat_key, 0) >= goal:
                completed.add(mission_id)
                SAVE["coins"] += reward
                self.unlock_notice = f"MISSAO CONCLUIDA: {name}  +{reward} MOEDAS"
                self.unlock_notice_timer = 5.0
                AUDIO.play("unlock", 1.0)
                changed = True
        if changed:
            SAVE["completed_missions"] = sorted(completed)
            save_data(SAVE)
            self.check_progress_achievements()

    def add_mission_progress(self, stat_key, amount=1):
        if self.mode != "arena" or is_beta_character(self.player.character):
            return
        char = self.player.character
        stats = self.mission_stats_for(char)
        stats[stat_key] = stats.get(stat_key, 0) + amount
        self.check_character_missions(char)

    def check_special_character_unlocks_on_wave_clear(self):
        """Unlocks da V14 que dependem de feitos completos da run, nao do inicio da wave."""
        if self.mode != "arena" or is_beta_character(self.player.character):
            return
        difficulty_rank = DIFFICULTY_ORDER.index(getattr(self,"difficulty","easy")) if getattr(self,"difficulty","easy") in DIFFICULTY_ORDER else 0
        if (self.game_mode == "normal" and self.wave >= 30 and difficulty_rank >= DIFFICULTY_ORDER.index("normal")
                and not SAVE.get("strikada_unlocked", False)):
            SAVE["strikada_unlocked"] = True
            save_data(SAVE)
            AUDIO.play("unlock", 1.0)
            self.unlock_notice = "STRIKADA EGOISTA DESBLOQUEADO!"
            self.unlock_notice_timer = 6.0

    def update_mission_wave(self):
        if self.mode != "arena" or is_beta_character(self.player.character):
            return
        char = self.player.character
        stats = self.mission_stats_for(char)
        if self.wave > stats.get("best_wave", 0):
            stats["best_wave"] = self.wave
            self.check_character_missions(char)
        # V14 FINAL: todos os marcos de onda agora vivem dentro da escala 1-100.
        for key, (metric, goal) in ACHIEVEMENT_PROGRESS_RULES.items():
            if metric == "wave" and self.wave >= goal:
                self.unlock_achievement(key)
        self.check_progress_achievements()

    def spawn_ruan_servant(self, enemy, force=False):
        if self.player.character != "Ruan":
            return
        if not force and self.current_damage_kind != "ruan_dash":
            return
        if isinstance(enemy, TrainingDummy):
            return
        servant = RuanServant(pygame.Vector2(enemy.pos), enemy, self.player, guardian=False)
        self.servants.append(servant)
        self.damage_texts.append(DamageText("NOVO AMIGO!", pygame.Vector2(enemy.pos), GREEN, 0.9))
        if sum(1 for x in self.servants if not x.dead and not x.guardian) >= 12:
            self.unlock_achievement("friend_12")

    def trigger_hank_explosion(self, pos, damage, radius, exclude=None, artillery=False, domain_charge_raw=0.0):
        pos=pygame.Vector2(pos); radius=float(radius)
        self.hank_explosions.append({"pos":pos,"timer":0.42,"total":0.42,"radius":radius,"artillery":artillery})
        old=self.current_damage_kind; self.current_damage_kind="hank_artillery" if artillery else "hank_shell_explosion"
        hit_any=False
        for e in list(self.enemies):
            if e.dead or e is exclude: continue
            if e.pos.distance_to(pos)<=radius+e.radius:
                e.damage(damage*self.player.effective_damage_mult(self,e,self.current_damage_kind,e.pos.distance_to(self.player.pos)),self,pos)
                hit_any=True
        maho=getattr(self,"mahoraga",None)
        if maho is not None and not maho.dead and maho is not exclude and maho.pos.distance_to(pos)<=radius+maho.radius:
            maho.take_damage(damage*self.player.effective_damage_mult(self,None,self.current_damage_kind,maho.pos.distance_to(self.player.pos)),self,pos,from_player=True)
            hit_any=True
        self.current_damage_kind=old
        if hit_any and domain_charge_raw > 0.0:
            self.domain_charge_primary_hit(domain_charge_raw)
        self.spawn_particles(pos,RED if artillery else ORANGE,32 if artillery else 22); self.spawn_particles(pos,YELLOW,14 if artillery else 8)
        self.shake=max(self.shake,S(18 if artillery else 13)); self.flash_screen=max(self.flash_screen,0.08 if artillery else 0.05); AUDIO.play("hank_blast",1.0 if artillery else 0.86,65)
        return hit_any

    def domain_charge_primary_hit(self, raw_amount=20.0):
        """Credita um ataque principal que realmente conectou."""
        self.add_domain_charge(float(raw_amount))

    def projectile_domain_charge_value(self, pr):
        """Consome uma parcela de recarga pertencente a este projetil."""
        raw = float(getattr(pr, "domain_charge_raw", 0.0) or 0.0)
        uses = int(getattr(pr, "domain_charge_uses_left", 0) or 0)
        if raw <= 0.0 or uses <= 0:
            return 0.0
        pr.domain_charge_uses_left = uses - 1
        return raw

    def add_domain_charge(self, amount):
        # V15 GLOBAL: o orcamento de cada ataque e dividido por 5, mirando ~25 ataques bem acertados.
        # A fonte principal continua sendo ACERTOS nos inimigos, nao a morte deles.
        # Depois de ativar, a barra continua travada em 0 ate o Dominio terminar.
        if self.domain_active:
            return
        amount *= (1.0 / 5.0)
        if self.player.character == "Vasco" and getattr(self.player, "vasco_jackpot_timer", 0.0) > 0:
            return
        if getattr(self,"game_mode","normal")=="infinite":
            amount *= (0.80 ** self.infinite_curses.count("domain"))
        mult = (2.0 if self.player.devil_pact else 1.0) * (1.0 + 0.06 * SAVE.get("domain_level", 0))
        pr=getattr(self.player,"passive_domain_recharge",0.0)
        mult *= 1.0/max(0.10,1.0-pr)
        if self.player_in_boss_domain("void"):
            mult *= 0.30
        self.domain_charge = clamp(self.domain_charge + amount * mult, 0, 100)

    def is_in_domain(self, pos):
        return self.domain_active and pygame.Vector2(pos).distance_to(self.domain_center) <= self.domain_radius

    def handle_powerup_hit(self, enemy, amount, source_pos=None):
        """Efeitos centralizados dos Power Ups 2.0 disparados em acertos reais."""
        p=self.player; source=getattr(self,"current_damage_kind",None) or ""
        melee={"sword","execute","ruan_dash","father_wave","sans_melee_bone","hank_knives","glonk_100"}
        if p.hybrid_blade_vampire and source in melee:
            p.hybrid_melee_hits += 1
            if p.hybrid_melee_hits >= 6:
                p.hybrid_melee_hits = 0; p.heal(p.max_hp*0.04,self)
        if p.character=="Kayk" and p.kayk_soul_mark and source=="dual_pistol" and not enemy.dead:
            enemy.kayk_soul_hits=getattr(enemy,"kayk_soul_hits",0)+1
            if enemy.kayk_soul_hits>=5:
                enemy.kayk_soul_hits=0
                old=self.current_damage_kind; self.current_damage_kind="soul_mark_explosion"
                for other in list(self.enemies):
                    if not other.dead and other.pos.distance_to(enemy.pos)<=S(120):
                        other.damage(p.base_damage*0.85*p.effective_damage_mult(self,other,"soul_shot",other.pos.distance_to(p.pos)),self,enemy.pos,minimal_fx=True)
                self.current_damage_kind=old; self.spawn_particles(enemy.pos,PURPLE,12)
        if p.character==LIRA_KEY and source=="lira_censor" and p.lira_four_words and not enemy.dead and not isinstance(enemy,Boss) and random.random()<0.25:
            stats=[x for x in ("strength","speed","resistance","intelligence") if enemy.lira_censor.get(x,0)<0.60]
            if stats: enemy.apply_lira_censor(random.choice(stats),0.20,self)
        if p.character=="Vinicius 13" and p.vinicius_truly_automatic and source=="vinicius_bolt":
            for t in self.vinicius_turrets:
                if not t.dead and t.kind in ("random","shot","anti_titan","ballistic"): t.cd=0.0
        if p.character=="Potential Man" and p.potential_amphibian_shadow and source=="potential_frogs":
            enemy.forge_slow_timer=max(getattr(enemy,"forge_slow_timer",0.0),2.0)
        if p.character=="Ycaro" and p.ycaro_wrong_room and source=="shotgun" and source_pos is not None:
            dist=enemy.pos.distance_to(p.pos)
            if dist<=S(180):
                away=enemy.pos-p.pos
                if away.length_squared()>0: enemy.pos += away.normalize()*S(55)
                others=[o for o in self.enemies if o is not enemy and not o.dead and o.pos.distance_to(enemy.pos)<=S(75)+o.radius]
                if others:
                    o=min(others,key=lambda x:x.pos.distance_to(enemy.pos)); old=self.current_damage_kind; self.current_damage_kind="shotgun_collision"
                    o.damage(max(1.0,amount*0.45),self,enemy.pos,minimal_fx=True); self.current_damage_kind=old
        if p.character=="Colosso do Caos" and p.father_i_rule_here and source=="father_wave":
            enemy.forge_slow_timer=max(getattr(enemy,"forge_slow_timer",0.0),2.5)
            enemy.powerup_damage_down_timer=max(getattr(enemy,"powerup_damage_down_timer",0.0),2.5)

    def register_combo_hit(self):
        self.combo = min(50, self.combo + 1)
        self.combo_timer = 5.0 if getattr(self.player,"combo_engine",False) else 3.0
        if self.combo >= 50:
            self.unlock_achievement("combo_50")
        if self.player.vampire_heart and self.combo > 0 and self.combo % 8 == 0:
            self.player.heal(max(2, self.player.max_hp * 0.025), self)

    def award_passive_critical_kill(self, enemy):
        if enemy is None or not getattr(enemy,"dead",False) or getattr(self.player,"passive_crit_kill_coins",0.0)<=0:
            return
        reward_mult=difficulty_cfg(getattr(self,"difficulty","easy"))["reward"] if self.mode=="arena" else 1.0
        coin_value=getattr(enemy,"coin_value",0)
        if coin_value<=0:return
        extra=max(1,int(coin_value*self.coin_multiplier*reward_mult*(1.0+0.05*SAVE.get("coin_level",0))*max(.10,1.0+self.player.passive_coin_bonus)*self.player.passive_crit_kill_coins))
        self.run_coins += extra
        self.damage_texts.append(DamageText(f"FORTUNA +{extra}",pygame.Vector2(enemy.pos),PASSIVE_RARITIES["shiny"]["color"],0.55))

    def on_enemy_killed(self, enemy):
        # V15: matar nao da mais carga de Dominio; a carga vem dos acertos.
        if self.game_mode=="rogue" and self.rogue_rule=="glass":
            # Regra caotica: mortes deixam uma pequena explosao hostil e ofensiva.
            if enemy.pos.distance_to(self.player.pos)<=S(120): self.player.take_damage(self.player.max_hp*0.04,self)
        p = self.player
        # POWER UPS 2.0: efeitos de abate.
        if p.character=="Kevyn" and p.kevyn_thirsty_blade and self.current_damage_kind in ("sword","execute"):
            p.attack_cd=min(p.attack_cd,0.06)
        if p.character=="Glonk 100% Power" and p.glonk_learned and self.current_damage_kind=="glonk_100":
            p.base_damage += 1.0; self.damage_texts.append(DamageText("GLONK +1 DANO",pygame.Vector2(p.pos),GREEN,0.45))
        if p.character=="Kayk" and p.kayk_ballistic_procession and self.current_damage_kind in ("dual_pistol","soul_mark_explosion"):
            opts=[e for e in self.enemies if not e.dead and e is not enemy]
            if opts:
                t=min(opts,key=lambda e:e.pos.distance_to(enemy.pos)); d=t.pos-enemy.pos
                if d.length_squared()>0:
                    pr=Projectile(enemy.pos,d.normalize()*S(760),p.base_damage*0.75*p.projectile_bonus,"player",S(7),PURPLE,1.6,0); pr.kind="soul_shot"; pr.origin=pygame.Vector2(enemy.pos); pr.domain_charge_raw=0; pr.domain_charge_uses_left=0; self.projectiles.append(pr)
        if p.hybrid_overpressure and self.current_damage_kind in ("father_wave","hank_shell_explosion","hank_artillery","pineapple_explosion","sukuna_fuuga"):
            self.delayed_blasts.append({"timer":0.08,"pos":pygame.Vector2(enemy.pos),"radius":S(90),"damage":p.base_damage*0.35,"color":ORANGE})
        if p.character == "Vinicius 13" and self.mode == "arena":
            self.vinicius_scrap = min(20, self.vinicius_scrap + 1); self.vinicius_mini_kills += 1
            if self.vinicius_mini_kills >= (4 if p.vinicius_premium_scrap else 5):
                self.vinicius_mini_kills=0; self.spawn_vinicius_mini_turret()
            if self.vinicius_scrap>=20 and not any(t.mega and not t.dead for t in self.vinicius_turrets): self.open_vinicius_mega_choice()
        if self.mode == "arena" and not is_beta_character(p.character):
            SAVE["total_kills"] = SAVE.get("total_kills", 0) + 1
            self.add_mission_progress("kills", 1)
            total=SAVE.get("total_kills",0)
            if total >= 100: self.unlock_achievement("kill_100")
            if total >= 1000: self.unlock_achievement("kill_1000")
            if total >= 5000: self.unlock_achievement("kill_5000")
            if total >= 10000: self.unlock_achievement("kill_10000")
            self.check_progress_achievements()
        if self.domain_clash_active:
            self.domain_clash_score += 6.0
        if p.character == "Ruan" and self.current_damage_kind == "ruan_dash":
            self.spawn_ruan_servant(enemy)
            p.ruan_direct_kills += 1
            if p.ruan_forced_recruitment and random.random()<0.35:
                before=len(self.servants); self.spawn_ruan_servant(enemy)
                if len(self.servants)>before:
                    serv=self.servants[-1]; serv.max_hp*=0.60; serv.hp=min(serv.hp,serv.max_hp); serv.damage*=0.65
            if p.ruan_endless_army and p.ruan_direct_kills%5==0:
                before=len(self.servants); self.spawn_ruan_servant(enemy)
                if len(self.servants)>before:
                    serv=self.servants[-1]; serv.max_hp*=0.50; serv.hp=min(serv.hp,serv.max_hp); serv.damage*=0.55
        if p.character == "Colosso do Caos" and p.father_boss_heal and isinstance(enemy, Boss):
            p.heal(p.max_hp * 0.30, self)
        if isinstance(enemy,Boss) and p.character == SUKUNA_KEY and self.mode == "arena":
            p.gain_sukuna_finger(self)
            if p.sukuna_king_curses and random.random()<0.35:
                p.gain_sukuna_finger(self)
        if isinstance(enemy,Boss) and "bounty_hunter" in getattr(p,"passive_keys",[]):
            p.heal(p.max_hp*0.10,self)
        if p.kill_stamina:
            p.recover_stamina(p.kill_stamina, self)
        if p.predator:
            p.predator_timer = 3.0
        if p.insatiable_hunger:
            p.heal(max(2, p.max_hp * 0.035), self)
        if enemy.blood_marked:
            p.heal(max(8, p.max_hp * 0.10), self)
            self.damage_texts.append(DamageText("PRESA CONSUMIDA", pygame.Vector2(enemy.pos), GREEN))
        if p.chain_execution and self.current_damage_kind == "execute":
            options = [e for e in self.enemies if not e.dead and e is not enemy]
            if options:
                target = min(options, key=lambda e: e.pos.distance_to(enemy.pos))
                target.blood_marked = True
                self.damage_texts.append(DamageText("MARCADO", pygame.Vector2(target.pos), RED))
        if p.character == "Kevyn" and p.kevyn_hungry_sword and self.current_damage_kind in ("sword", "execute"):
            self.kevyn_sword_kills += 1
            self.kevyn_sword_kill_timer = 5.0
            if self.kevyn_sword_kills >= 3:
                self.kevyn_sword_kills = 0
                p.heal(max(12, p.max_hp * 0.08), self)
        if p.character == "Ycaro" and p.ycaro_domino and self.current_damage_kind == "shotgun":
            old = self.current_damage_kind
            self.current_damage_kind = "domino"
            for other in list(self.enemies):
                if other is not enemy and not other.dead and other.pos.distance_to(enemy.pos) <= S(145):
                    other.damage(p.base_damage * 0.80 * p.damage_mult, self, enemy.pos)
            self.current_damage_kind = old

    def spawn_vinicius_mini_turret(self):
        if self.player.character!="Vinicius 13": return False
        minis=[t for t in self.vinicius_turrets if not t.dead and not t.mega]
        if len(minis)>=5: self.damage_texts.append(DamageText("MINI TORRETAS 5/5",pygame.Vector2(self.player.pos),GRAY,0.65)); return False
        kind=random.choice(["heal","random","shot","wall"]); pos=self.player.pos+vec_from_angle(random.random()*math.tau)*S(95); pos.x=clamp(pos.x,S(70),W-S(70)); pos.y=clamp(pos.y,S(220),H-S(390)); self.vinicius_turrets.append(ViniciusTurret(pos,kind,self.player,False))
        if self.player.vinicius_production_line and len([t for t in self.vinicius_turrets if not t.dead and not t.mega])<5 and random.random()<0.30:
            pos2=pos+vec_from_angle(random.random()*math.tau)*S(70); pos2.x=clamp(pos2.x,S(70),W-S(70)); pos2.y=clamp(pos2.y,S(220),H-S(390)); extra=ViniciusTurret(pos2,random.choice(["heal","random","shot","wall"]),self.player,False); extra.max_hp*=0.50; extra.hp=extra.max_hp; self.vinicius_turrets.append(extra)
            self.damage_texts.append(DamageText("LINHA DE PRODUCAO!",pygame.Vector2(pos2),YELLOW,0.6))
        self.damage_texts.append(DamageText("TORRE "+ViniciusTurret.LABELS[kind],pygame.Vector2(pos),YELLOW,0.9)); AUDIO.play("upgrade",0.55,80); return True

    def open_vinicius_mega_choice(self):
        if self.state!="playing" or self.player.character!="Vinicius 13" or self.vinicius_scrap<20 or any(t.mega and not t.dead for t in self.vinicius_turrets): return False
        self.attack_held=self.parry_held=self.domain_held=self.dash_held=False; self.vinicius_mega_pending=True; self.state="vinicius_mega"; AUDIO.play("wave_clear",0.75); return True

    def build_vinicius_mega(self,kind):
        if kind not in ("hospital","anti_titan","ballistic") or self.vinicius_scrap<20 or any(t.mega and not t.dead for t in self.vinicius_turrets): return False
        self.vinicius_scrap-=20; self.vinicius_mega_pending=False; self.vinicius_mini_kills=0; pos=pygame.Vector2(W*0.58,H*0.50); self.vinicius_turrets.append(ViniciusTurret(pos,kind,self.player,True)); self.state="playing"; self.damage_texts.append(DamageText("MEGA TORRE: "+ViniciusTurret.LABELS[kind],pygame.Vector2(pos),DIVINE_BLUE,1.2)); AUDIO.play("boss",0.72,150); return True

    def open_upgrade(self):
        if self.state != "playing":
            return
        self.upgrade_return_mode = self.mode
        self.attack_held = False
        self.state = "upgrade"
        self.selected_upgrade_card = None
        self.upgrade_cards = self.generate_upgrades(3)

    def generate_upgrades(self, n):
        """65% globais/hibridos compativeis + 35% Assinatura do personagem."""
        character = self.player.character
        global_pool = [c for c in (UNIVERSAL_UPGRADES + HYBRID_UPGRADES) if upgrade_compatible(c, character)]
        signature_pool = list(CHARACTER_UPGRADES.get(character, []))

        def available(pool):
            return [
                c for c in pool
                if (c[3] in STACKABLE_UPGRADES or c[3] not in self.owned_upgrades)
                and not (c[3] == "quick_feet" and self.owned_upgrade_counts.get("quick_feet", 0) >= 6)
                and not (c[3] == "pierce" and self.owned_upgrade_counts.get("pierce", 0) >= 5)
                and not (c[3] == "crit" and self.owned_upgrade_counts.get("crit", 0) >= 5)
            ]

        global_pool = available(global_pool)
        signature_pool = available(signature_pool)
        weights = {"common":46, "rare":29, "epic":15, "legendary":7, "divine":1.4, "cursed":3}

        def weighted_pick(pool):
            if not pool:
                return None
            total = sum(weights.get(x[0], 1.0) for x in pool)
            roll = random.uniform(0, total)
            acc = 0.0
            for x in pool:
                acc += weights.get(x[0], 1.0)
                if roll <= acc:
                    return x
            return pool[-1]

        cards=[]
        for _ in range(n):
            if not global_pool and not signature_pool:
                break
            want_signature = random.random() < 0.35
            pool = signature_pool if want_signature and signature_pool else global_pool
            if not pool:
                pool = signature_pool
            pick = weighted_pick(pool)
            if pick is None:
                break
            cards.append(pick)
            if pick in global_pool and pick[3] not in STACKABLE_UPGRADES:
                global_pool.remove(pick)
            elif pick in signature_pool:
                signature_pool.remove(pick)

        # "Encontrados" significa que a carta ja apareceu ao jogador ao menos uma vez.
        discovered=set(SAVE.get("upgrade_discovered", []))
        before=len(discovered)
        discovered.update(c[3] for c in cards)
        if len(discovered)!=before:
            SAVE["upgrade_discovered"]=sorted(discovered)
            save_data(SAVE)
        return cards

    def apply_upgrade(self, card):
        rarity, name, desc, key = card
        p = self.player
        self.owned_upgrades.add(key)
        self.owned_upgrade_counts[key] = self.owned_upgrade_counts.get(key, 0) + 1

        if key == "heart_reinforced":
            if p.character == "Glonk 100% Power":
                p.max_stamina += 12; p.recover_stamina(12)
            else:
                p.max_hp += 20; p.heal(20)
        elif key == "steel_lung": p.max_stamina += 20; p.recover_stamina(20)
        elif key == "second_wind": p.stamina_regen *= 1.25
        elif key == "heavy_hand": p.damage_mult *= 1.15
        elif key == "quick_feet":
            p.base_speed = min(p.base_speed * 1.10, S(620))
        elif key == "scavenger": p.drop_bonus += 0.08
        elif key == "battle_thirst": p.kill_stamina = max(p.kill_stamina, 5)
        elif key == "questionable_hemo": p.questionable_hemo = True
        elif key == "overclock": p.overclock = True
        elif key == "last_breath": p.last_breath = True
        elif key == "explosive_parry": p.explosive_parry = True
        elif key == "predator": p.predator = True
        elif key == "pierce": p.projectile_pierce += 1
        elif key == "crit": p.crit_chance += 0.12
        elif key == "ghost_dash": p.ghost_dash = True
        elif key == "blood_debt": p.blood_debt = True
        elif key == "vampire_heart": p.vampire_heart = True
        elif key == "orb_rain": p.orb_rain = True
        elif key == "profane_ricochet": p.ricochet_chance = max(p.ricochet_chance, 0.35)
        elif key == "chain_execution": p.chain_execution = True
        elif key == "beyond_limit": p.beyond_limit = True; p.recover_stamina(p.max_stamina*0.30)
        elif key == "second_bar": p.second_bar = True
        elif key == "broken_time": p.broken_time = True
        elif key == "giant_hunter": p.giant_hunter = True
        elif key == "orb_black_hole": p.orb_magnet = True
        elif key == "eternal_combo": p.eternal_combo = True
        elif key == "domain_evolution": p.domain_evolution = True
        elif key == "glass_cannon":
            p.glass_cannon = True; p.damage_mult *= 2.0
            if p.character in ("Sans", "Glonk 100% Power"):
                p.max_hp = 1; p.hp = min(p.hp, 1)
            else:
                p.max_hp = max(30, p.max_hp*0.65); p.hp = min(p.hp, p.max_hp)
        elif key == "insatiable_hunger": p.insatiable_hunger = True
        elif key == "devil_pact": p.devil_pact = True
        elif key == "no_brakes": p.no_brakes = True; p.damage_mult *= 1.40
        elif key == "one_last_game": p.one_last_game = True
        elif key == "god_not_watching": p.god_not_watching = True
        # Ana
        elif key == "ana_blind_spot": p.ana_blind_spot = True
        elif key == "ana_phase_bullet": p.ana_blast_mult *= 1.35
        elif key == "ana_double_shot": p.ana_double_shot = True
        elif key == "ana_reality_error": p.ana_reality_error = max(p.ana_reality_error, 0.20)
        elif key == "ana_impossible_shot": p.ana_miniana_speed *= 1.55
        elif key == "ana_vector_step": p.ana_vector_step = True
        elif key == "ana_causal_eye": p.ana_causal_eye = True; p.crit_chance += 0.10
        elif key == "ana_reality_exe": p.ana_reality_exe = True; p.domain_evolution = True
        # Kevyn
        elif key == "kevyn_wide_blade": p.kevyn_sword_range *= 1.35
        elif key == "kevyn_rupture": p.kevyn_sword_cost_reduction = 1
        elif key == "kevyn_impossible_weight": p.kevyn_sword_bonus *= 1.25
        elif key == "kevyn_human_wall": p.kevyn_human_wall = True
        elif key == "kevyn_time_counter": p.kevyn_time_counter = True
        elif key == "kevyn_immovable": p.kevyn_immovable = True
        elif key == "kevyn_hungry_sword": p.kevyn_hungry_sword = True
        elif key == "kevyn_time_stops": p.kevyn_time_stops = True; p.domain_evolution = True
        # Ycaro
        elif key == "ycaro_point_blank": p.ycaro_point_blank = True
        elif key == "ycaro_more_pellets": p.ycaro_extra_pellets += 2
        elif key == "ycaro_hot_powder": p.ycaro_pellet_speed *= 1.25
        elif key == "ycaro_domino": p.ycaro_domino = True
        elif key == "ycaro_aggressive_reload": p.ycaro_aggressive_reload = True
        elif key == "ycaro_sawed_off": p.ycaro_sawed_off = True
        elif key == "ycaro_hunter": p.ycaro_hunter = True
        elif key == "ycaro_no_too_close": p.ycaro_no_too_close = True; p.domain_evolution = True
        # Kayk
        elif key == "kayk_extra_pair": p.kayk_extra_pair += 1
        elif key == "kayk_soul_pierce": p.kayk_soul_pierce += 1
        elif key == "kayk_funeral_tax": p.kill_stamina = max(p.kill_stamina, 7)
        elif key == "kayk_dead_echo": p.ricochet_chance = max(p.ricochet_chance, 0.60)
        elif key == "kayk_spectral_step": p.kayk_spectral_step = True
        elif key == "kayk_posthumous_ammo": p.kayk_pistol_bonus *= 1.30
        elif key == "kayk_armed_procession": p.kayk_armed_procession = True; p.domain_evolution = True
        elif key == "kayk_thousand_souls": p.kayk_thousand_souls = True; p.domain_evolution = True
        # Pedro
        elif key == "pedro_ripe_fruit": p.pedro_damage_mult *= 1.30
        elif key == "pedro_spiny_path": p.pedro_speed_mult *= 1.30; p.pedro_range_mult *= 1.30
        elif key == "pedro_round_trip": p.pedro_return_hit = True; p.pedro_return_damage_mult *= 1.35
        elif key == "pedro_explosive_pineapple": p.pedro_explosive = True
        elif key == "pedro_double_harvest": p.pedro_extra_boomerangs += 1
        elif key == "pedro_steel_peel": p.pedro_steel_peel = True
        elif key == "pedro_pineapple_crown": p.pedro_crown = True
        elif key == "pedro_x_destiny": p.pedro_x_destiny = True; p.domain_evolution = True
        # Ruan
        elif key == "ruan_brutal_charge": p.ruan_dash_damage_mult *= 1.30
        elif key == "ruan_fallen_pact": p.ruan_servant_hp_mult *= 1.50
        elif key == "ruan_pack_hunger": p.ruan_servant_damage_mult *= 1.35
        elif key == "ruan_war_command": p.ruan_servant_speed_mult *= 1.35
        elif key == "ruan_necro_step": p.ruan_necro_step = True
        elif key == "ruan_growing_army": p.ruan_growing_army = True
        elif key == "ruan_royal_guard": p.ruan_guardian_mult *= 1.70; p.domain_evolution = True
        elif key == "ruan_king_dead": p.ruan_king_dead = True; p.domain_evolution = True
        # Strikada Egoista
        elif key == "strikada_more_bounces": p.strikada_bounces += 2
        elif key == "strikada_homing": p.strikada_homing = True
        elif key == "strikada_two_balls": p.strikada_extra_balls = 1
        elif key == "strikada_kill_explosion": p.strikada_kill_explosion = True
        # Colosso do Caos jogavel
        elif key == "father_wave": p.father_radius_mult *= 1.25
        elif key == "father_slap": p.father_damage_mult *= 1.30
        elif key == "father_lung": p.max_stamina += 30; p.recover_stamina(30)
        elif key == "father_authority": p.father_clear_projectiles = True
        elif key == "father_family_issues": p.father_boss_bonus = True
        elif key == "father_present": p.father_boss_heal = True
        elif key == "father_sentence_circle": p.father_domain_radius_mult *= 1.35; p.domain_evolution = True
        elif key == "father_final_word": p.father_domain_refill = True; p.domain_evolution = True

        # === POWER UPS 2.0: universais hibridos e assinaturas ===
        if key == "steady_hands": p.passive_attack_speed += 0.12
        elif key == "field_medic": p.passive_wave_heal += 0.05
        elif key == "combo_engine": p.combo_engine = True
        elif key == "blade_vampire": p.hybrid_blade_vampire = True
        elif key == "chaotic_ammo": p.hybrid_chaotic_ammo = True
        elif key == "supreme_command": p.hybrid_supreme_command = True; p.summon_power_mult = max(p.summon_power_mult, 1.25)
        elif key == "inertia": p.hybrid_inertia = True
        elif key == "overpressure": p.hybrid_overpressure = True
        elif key == "resonant_domain": p.hybrid_resonant_domain = True
        elif key == "auto_loader": p.hybrid_auto_loader = True
        elif key == "kinetic_rebound": p.hybrid_kinetic_rebound = True

        # Ana — Realidade / Mini-Anas
        elif key == "ana_pocket_army": p.ana_pocket_army = True
        elif key == "ana_continuity": p.ana_continuity = True
        elif key == "ana_all_ana": p.ana_all_ana = True
        elif key == "ana_unstable_reality": p.ana_unstable_reality = True
        # Kevyn — espada / parry
        elif key == "kevyn_second_cut": p.kevyn_second_cut = True
        elif key == "kevyn_thirsty_blade": p.kevyn_thirsty_blade = True
        elif key == "kevyn_absolute_parry": p.kevyn_absolute_parry = True
        elif key == "kevyn_one_vs_hundred": p.kevyn_one_vs_hundred = True
        # Ycaro — shotgun
        elif key == "ycaro_heavy_lead": p.ycaro_heavy_lead = True
        elif key == "ycaro_twelve_barrels": p.ycaro_twelve_barrels = True
        elif key == "ycaro_wounded_hunter": p.ycaro_wounded_hunter = True
        elif key == "ycaro_wrong_room": p.ycaro_wrong_room = True
        # Kayk — pistolas
        elif key == "kayk_crossfire": p.kayk_crossfire = True
        elif key == "kayk_soul_mark": p.kayk_soul_mark = True
        elif key == "kayk_two_triggers": p.kayk_two_triggers = True
        elif key == "kayk_ballistic_procession": p.kayk_ballistic_procession = True
        # Pedro — abacaxi
        elif key == "pedro_saturn": p.pedro_saturn = True
        elif key == "pedro_double_crop": p.pedro_double_crop = True
        elif key == "pedro_predator_fruit": p.pedro_predator_fruit = True
        elif key == "pedro_industrial_plantation": p.pedro_industrial_plantation = True
        # Ruan — dash / amigos
        elif key == "ruan_forced_recruitment": p.ruan_forced_recruitment = True
        elif key == "ruan_attack_formation": p.ruan_attack_formation = True
        elif key == "ruan_no_one_left": p.ruan_no_one_left = True
        elif key == "ruan_endless_army": p.ruan_endless_army = True
        # Colosso do Caos
        elif key == "father_growing_authority": p.father_growing_authority = True
        elif key == "father_repeat_slap": p.father_repeat_slap = True
        elif key == "father_i_rule_here": p.father_i_rule_here = True
        elif key == "father_paternal_sentence": p.father_paternal_sentence = True
        # Vinicius 13
        elif key == "vinicius_premium_scrap": p.vinicius_premium_scrap = True
        elif key == "vinicius_auto_maintenance": p.vinicius_auto_maintenance = True
        elif key == "vinicius_production_line": p.vinicius_production_line = True
        elif key == "vinicius_truly_automatic": p.vinicius_truly_automatic = True
        # Strikada
        elif key == "strikada_self_pass": p.strikada_self_pass = True
        elif key == "strikada_metavision": p.strikada_metavision = True
        elif key == "strikada_protagonist": p.strikada_protagonist = True
        elif key == "strikada_impossible_goal": p.strikada_impossible_goal = True
        # Glonk 100% Power
        elif key == "glonk_2_power": p.base_damage *= 2.0
        elif key == "glonk_industrial_tongue": p.glonk_industrial_tongue = True
        elif key == "glonk_learned": p.glonk_learned = True
        elif key == "glonk_101_power": p.glonk_101_power = True; p.glonk_101_ready = True
        # Vasco
        elif key == "vasco_marked_chip": p.vasco_marked_chip = True
        elif key == "vasco_high_stakes": p.vasco_high_stakes = True
        elif key == "vasco_sevens": p.vasco_sevens = True
        elif key == "vasco_house_loses": p.vasco_house_loses = True; p.vasco_bet_level = max(p.vasco_bet_level, 60.0); p.vasco_jackpot_duration = 10.0
        # Lira
        elif key == "lira_thick_bar": p.lira_thick_bar = True
        elif key == "lira_four_words": p.lira_four_words = True
        elif key == "lira_torn_page": p.lira_torn_page = True
        elif key == "lira_nothing_published": p.lira_nothing_published = True
        # Hank
        elif key == "hank_high_caliber": p.hank_high_caliber = True
        elif key == "hank_bolt_cycle": p.hank_bolt_cycle = True; p.hank_charge_required = max(0.85, p.hank_charge_required - 0.40)
        elif key == "hank_confirmed_target": p.hank_confirmed_target = True
        elif key == "hank_madness_combat": p.hank_madness_combat = True
        # Potential Man
        elif key == "potential_coordinated_pack": p.potential_coordinated_pack = True
        elif key == "potential_amphibian_shadow": p.potential_amphibian_shadow = True
        elif key == "potential_early_wheel": p.potential_early_wheel = True
        elif key == "potential_ten_shadows_general": p.potential_ten_shadows_general = True
        # Sukuna
        elif key == "sukuna_dismantle": p.sukuna_dismantle = True
        elif key == "sukuna_adaptive_cut": p.sukuna_adaptive_cut = True
        elif key == "sukuna_open_furnace": p.sukuna_open_furnace = True
        elif key == "sukuna_king_curses": p.sukuna_king_curses = True
        # Sans
        elif key == "sans_stubborn_bone": p.sans_stubborn_bone = True
        elif key == "sans_blue_shortcut": p.sans_blue_shortcut = True
        elif key == "sans_karmic_judgement": p.sans_karmic_judgement = True
        elif key == "sans_worse_time": p.sans_worse_time = True
        # Rip_Indra
        elif key == "rip_tushita_quest": p.rip_sword_damage_mult *= 1.30
        elif key == "rip_admin_abuse": p.rip_range_mult *= 1.25; p.rip_sword_damage_mult *= 1.10
        elif key == "rip_triple_authority": p.rip_triple_authority = True
        elif key == "rip_admin_rage": p.rip_admin_rage = True
        # Hisoka
        elif key == "hisoka_card_trick": p.hisoka_card_trick = True
        elif key == "hisoka_elastic_gum": p.hisoka_elastic_gum = True
        elif key == "hisoka_paralyzing_joker": p.hisoka_paralyzing_joker = True
        elif key == "hisoka_show_must_go_on": p.hisoka_show_must_go_on = True
        # Glonk normal
        elif key == "glonk_runs": p.base_speed = max(p.base_speed, S(285))
        elif key == "glonk_not_supposed": p.glonk_not_supposed = True
        elif key == "glonk_professional_coward": p.glonk_professional_coward = True
        elif key == "glonk_last_one": p.glonk_last_one = True

        p.passive_on_upgrade(self)
        AUDIO.play("upgrade", 0.90)
        self.check_synergies()
        self.state = "playing"
        self.mode = self.upgrade_return_mode
        if getattr(self,"suppress_upgrade_advance",False):
            return
        if self.mode == "afk":
            if not any(isinstance(e, TrainingDummy) for e in self.enemies):
                self.spawn_training_dummy()
        else:
            self.wave += 1
            self.healing_locked = (self.game_mode=="extinction")
            self.spawn_wave()

    def check_synergies(self):
        for req, name, desc in UPGRADE_SYNERGIES:
            if req.issubset(self.owned_upgrades) and name not in self.synergies:
                self.synergies.add(name)
                AUDIO.play("synergy", 1.0)
                self.synergy_name = name
                self.synergy_timer = 3.2
                self.damage_texts.append(DamageText("SINERGIA!", pygame.Vector2(self.player.pos), YELLOW, 1.2))
                if name == "GEOMETRIA IMPOSSIVEL":
                    self.player.ana_miniana_speed *= 1.20
                    self.player.ana_reality_error = max(self.player.ana_reality_error, 0.30)
                    self.player.ana_blast_mult *= 1.15
                elif name == "EXECUCAO BALISTICA":
                    self.player.ycaro_extra_pellets += 1
                elif name == "PACTO DE SOBREVIVENCIA":
                    self.player.stamina_regen *= 1.15
                elif name == "COLHEITA DE GUERRA":
                    self.player.pedro_damage_mult *= 1.15
                elif name == "MARCHA DOS AMIGOS":
                    self.player.ruan_servant_damage_mult *= 1.15
                elif name == "REALIDADE RECURSIVA":
                    self.player.ana_miniana_speed *= 1.25
                elif name == "ARTILHARIA DE BOLSO":
                    self.player.hank_charge_required=max(0.85,self.player.hank_charge_required-0.12)
                elif name == "FUNERAL EM RAJADA":
                    self.player.kayk_procession_bonus=True
                elif name == "COZINHA MALEVOLENTE":
                    self.player.sukuna_fuuga_synergy=True

    def update_joystick(self, pos):
        rect = self.buttons.get("joystick")
        if rect is None:
            self.joystick_vector.update(0, 0)
            return
        center = pygame.Vector2(rect.center)
        delta = pygame.Vector2(pos) - center
        radius = max(1.0, min(rect.w, rect.h) * 0.46)
        length = delta.length()
        if length < radius * 0.14:
            self.joystick_vector.update(0, 0)
        elif length > 0:
            self.joystick_vector = delta / max(radius, length)

    def uses_aim_stick(self):
        # No Dominio do Hank o canhao vira facas de curtissimo alcance: o analogico de mira
        # vira um botao simples para combinar com o kit corpo a corpo e reduzir custo de UI.
        if self.player.character == HANK_KEY and self.domain_active:
            return False
        return self.player.character in ("Kayk", "Ycaro", "Pedro", "Vasco", LIRA_KEY, HANK_KEY)

    def update_aim_stick(self, pos):
        rect = self.buttons.get("attack")
        if rect is None:
            return
        center = pygame.Vector2(rect.center)
        delta = pygame.Vector2(pos) - center
        radius = max(1.0, min(rect.w, rect.h) * 0.46)
        length = delta.length()
        if length >= radius * 0.10:
            self.aim_vector = delta / max(radius, length)
            if self.aim_vector.length_squared() > 1.0:
                self.aim_vector = self.aim_vector.normalize()

    def attack_direction(self):
        if self.uses_aim_stick() and self.aim_active and self.aim_vector.length_squared() > 0.01:
            return self.aim_vector.normalize()
        f = pygame.Vector2(self.player.facing)
        return f.normalize() if f.length_squared() else pygame.Vector2(1,0)

    def handle_touch_motion(self, pos, finger_id=None):
        if self.state != "playing":
            return
        if finger_id is not None:
            if self.joystick_finger == finger_id:
                self.update_joystick(pos)
            if self.aim_finger == finger_id:
                self.update_aim_stick(pos)
        else:
            if self.joystick_mouse_active:
                self.update_joystick(pos)
            if self.aim_mouse_active:
                self.update_aim_stick(pos)

    def handle_touch_down(self, pos, finger_id=None):
        if self.state == "playing" and (getattr(self, "mahoraga_cutscene_active", False) or getattr(self, "sukuna_cutscene_active", False)):
            return
        if self.state == "playing":
            if self.game_mode=="arena_survival" and self.arena_reward_cards:
                for r,card in self.arena_reward_rects:
                    if r.collidepoint(pos): self.pick_arena_reward(card); return
            if self.buttons["pause"].collidepoint(pos):
                self.pause_game()
                return
            if self.mode == "afk":
                if self.afk_buttons["DUMMY"].collidepoint(pos):
                    self.spawn_training_dummy()
                    return
                if self.afk_buttons["INIMIGO"].collidepoint(pos):
                    self.spawn_afk_enemy()
                    return
                if self.afk_buttons["BOSS"].collidepoint(pos):
                    self.spawn_afk_boss()
                    return
                if self.afk_buttons["TIRO"].collidepoint(pos):
                    self.afk_test_shot()
                    return
                if self.afk_buttons["DOM"].collidepoint(pos):
                    self.domain_charge = 100
                    self.player.hp = self.player.max_hp
                    self.player.stamina = self.player.max_stamina
                    self.damage_texts.append(DamageText("DOMINIO 100%", pygame.Vector2(self.player.pos), PURPLE))
                    return
                if self.afk_buttons["UP"].collidepoint(pos):
                    self.open_upgrade()
                    return
            if self.buttons["joystick"].collidepoint(pos):
                self.update_joystick(pos)
                if finger_id is not None:
                    self.joystick_finger = finger_id
                    self.active_fingers[finger_id] = "joystick"
                else:
                    self.joystick_mouse_active = True
                return
            if self.buttons["attack"].collidepoint(pos):
                if self.uses_aim_stick():
                    self.aim_active = True
                    self.attack_held = True
                    self.update_aim_stick(pos)
                    if finger_id is not None:
                        self.aim_finger = finger_id
                        self.active_fingers[finger_id] = "aim"
                    else:
                        self.aim_mouse_active = True
                    # Hank mira enquanto segura: o canhao so dispara quando o jogador solta o joystick de mira.
                    if self.player.character != HANK_KEY:
                        self.player.attack(self)
                else:
                    self.attack_held = True
                    if finger_id is not None: self.active_fingers[finger_id] = "attack"
                    if self.player.character == "Potential Man":
                        self.player.potential_hold_timer=0.0; self.player.potential_hold_triggered=False
                    elif self.player.uses_special_attack_hold():
                        if self.player.character==RIP_INDRA_KEY: self.player.rip_hold_time=0.0
                        else: self.player.hisoka_hold_time=0.0
                    elif self.player.has_divine_attack_hold():
                        self.player.divine_attack_hold=0.0; self.player.divine_attack_triggered=False
                    else: self.player.attack(self)
            elif self.buttons["dash"].collidepoint(pos):
                if self.player.divine_ruan or self.player.divine_kayk or self.player.divine_pedro:
                    self.dash_held=True; self.player.divine_dash_hold=0.0; self.player.divine_dash_triggered=False
                    if finger_id is not None: self.active_fingers[finger_id]="dash_hold"
                else:
                    if finger_id is not None: self.active_fingers[finger_id]="action"
                    self.player.dash(self,self.get_move_dir())
            elif self.buttons["parry"].collidepoint(pos):
                if self.player.character == "Sans": self.player.fire_sans_blaster(self,auto=False)
                elif self.player.divine_kevyn:
                    self.parry_held=True; self.player.divine_parry_hold=0.0; self.player.divine_parry_triggered=False
                    if finger_id is not None: self.active_fingers[finger_id]="parry_hold"
                else: self.player.parry(self)
            elif self.buttons["domain"].collidepoint(pos):
                if self.player.divine_kevyn:
                    self.domain_held=True; self.player.divine_domain_hold=0.0; self.player.divine_domain_triggered=False
                    if finger_id is not None: self.active_fingers[finger_id]="domain_hold"
                elif self.player.character == HANK_KEY:
                    self.domain_held=True; self.player.hank_domain_hold=0.0; self.player.hank_domain_triggered=False
                    if finger_id is not None: self.active_fingers[finger_id]="domain_hold"
                elif self.player.character == SUKUNA_KEY:
                    self.domain_held=True; self.player.sukuna_domain_hold=0.0; self.player.sukuna_domain_triggered=False
                    if finger_id is not None: self.active_fingers[finger_id]="domain_hold"
                else: self.player.expand_domain(self)

    def handle_touch_up(self, pos, finger_id=None):
        if self.state == "playing" and (getattr(self, "mahoraga_cutscene_active", False) or getattr(self, "sukuna_cutscene_active", False)):
            return
        if finger_id is not None:
            action = self.active_fingers.pop(finger_id, None)
            if action in self.move_touch:
                self.move_touch[action] = False
            elif action == "joystick":
                if self.joystick_finger == finger_id:
                    self.joystick_finger = None
                    self.joystick_vector.update(0, 0)
            elif action == "aim":
                # Hank confirma a direcao no instante em que o dedo e solto.
                if self.player.character == HANK_KEY:
                    if self.aim_vector.length_squared() > 0.01:
                        self.player.facing = self.aim_vector.normalize()
                    self.player.attack(self)
                self.aim_finger = None
                self.aim_active = False
                self.attack_held = False
            elif action == "attack":
                if self.player.character == "Potential Man" and not self.player.potential_hold_triggered: self.player.attack(self)
                elif self.player.uses_special_attack_hold(): self.player.finish_special_attack_hold(self)
                elif self.player.has_divine_attack_hold(): self.player.finish_attack_hold(self)
                self.player.potential_hold_timer=0.0; self.player.potential_hold_triggered=False; self.attack_held=False
            elif action == "dash_hold":
                self.dash_held=False; self.player.finish_dash_hold(self)
            elif action == "parry_hold":
                self.parry_held=False; self.player.finish_parry_hold(self)
            elif action == "domain_hold":
                self.domain_held=False; self.player.finish_domain_hold(self)
        else:
            # mouse/desktop: não há ID de dedo
            for d in self.move_touch:
                self.move_touch[d] = False
            self.joystick_mouse_active = False
            self.joystick_vector.update(0, 0)
            # No desktop, Hank tambem dispara somente ao soltar o controle de mira.
            if self.attack_held and self.player.character == HANK_KEY:
                if self.aim_vector.length_squared() > 0.01:
                    self.player.facing = self.aim_vector.normalize()
                self.player.attack(self)
            self.aim_mouse_active = False
            self.aim_active = False
            self.aim_finger = None
            if self.attack_held and self.player.character != HANK_KEY:
                if self.player.character == "Potential Man" and not self.player.potential_hold_triggered: self.player.attack(self)
                elif self.player.uses_special_attack_hold(): self.player.finish_special_attack_hold(self)
                elif self.player.has_divine_attack_hold(): self.player.finish_attack_hold(self)
            if self.dash_held: self.dash_held=False; self.player.finish_dash_hold(self)
            if self.parry_held: self.parry_held=False; self.player.finish_parry_hold(self)
            if self.domain_held: self.domain_held=False; self.player.finish_domain_hold(self)
            self.player.potential_hold_timer=0.0; self.player.potential_hold_triggered=False; self.attack_held=False

    def get_move_dir(self):
        k = pygame.key.get_pressed()
        x = (1 if k[pygame.K_d] or k[pygame.K_RIGHT] else 0) - (1 if k[pygame.K_a] or k[pygame.K_LEFT] else 0)
        y = (1 if k[pygame.K_s] or k[pygame.K_DOWN] else 0) - (1 if k[pygame.K_w] or k[pygame.K_UP] else 0)
        x += (1 if self.move_touch["right"] else 0) - (1 if self.move_touch["left"] else 0)
        y += (1 if self.move_touch["down"] else 0) - (1 if self.move_touch["up"] else 0)
        keyboard_touch = pygame.Vector2(x, y)
        move = keyboard_touch + self.joystick_vector
        if move.length_squared() > 1.0:
            move = move.normalize()
        return move

    def update_playing(self, dt):
        if getattr(self, "mahoraga_cutscene_active", False):
            self.update_mahoraga_cutscene(dt)
            return
        if getattr(self, "sukuna_cutscene_active", False):
            self.update_sukuna_cutscene(dt)
            return
        self.check_beta_character_unlock_quests()
        if getattr(self, "sukuna_destruction_active", False):
            self.update_sukuna_destruction(dt)
        # EXTINCAO: trava o maior HP possivel no menor valor ja atingido.
        # Isso bloqueia ate futuras curas que eventualmente tentem alterar HP diretamente.
        if self.game_mode == "extinction":
            if self.extinction_hp_cap is None:
                self.extinction_hp_cap = self.player.hp
            self.player.hp = min(self.player.hp, self.extinction_hp_cap)
        self.time += dt
        self.domain_message_timer = max(0, self.domain_message_timer - dt)
        self.boss_domain_message_timer = max(0, self.boss_domain_message_timer - dt)
        self.clash_result_timer = max(0, self.clash_result_timer - dt)
        self.unlock_notice_timer = max(0, self.unlock_notice_timer - dt)
        self.wave_banner = max(0, self.wave_banner - dt)
        self.glonk_event_timer = max(0.0, self.glonk_event_timer-dt)
        self.glonk_boss_intro_timer = max(0.0, self.glonk_boss_intro_timer-dt)
        self.glonk_music_cut_timer = max(0.0, self.glonk_music_cut_timer-dt)
        self.slash_fx = max(0, self.slash_fx - dt)
        self.flash_screen = max(0, self.flash_screen - dt)
        self.father_wave_fx_timer = max(0, self.father_wave_fx_timer - dt)
        self.achievement_timer = max(0, self.achievement_timer - dt)
        self.synergy_timer = max(0, self.synergy_timer - dt)
        self.enemy_slow_timer = max(0, self.enemy_slow_timer - dt)
        self.orb_chain_timer = max(0, self.orb_chain_timer - dt)
        self.kevyn_sword_kill_timer = max(0, self.kevyn_sword_kill_timer - dt)
        if self.orb_chain_timer <= 0:
            self.orb_chain_count = 0
        if self.kevyn_sword_kill_timer <= 0:
            self.kevyn_sword_kills = 0
        if self.domain_active:
            # V11: a area permanece FIXA onde foi ativada.
            self.domain_timer -= dt
            if self.domain_timer <= 0:
                self.domain_active = False
                self.domain_timer = 0
                if self.bad_time_active:
                    self.bad_time_active=False
                    self.sans_bones=[]
                    self.damage_texts.append(DamageText("BAD TIME ENCERRADA",pygame.Vector2(self.player.pos),GRAY))
                else:
                    self.damage_texts.append(DamageText("DOMINIO ENCERRADO", pygame.Vector2(self.player.pos), GRAY))
                self.hank_domain_active = False
                self.hank_domain_trapped_ids = set()
                self.player.hank_cannon_planted = False
                self.hank_cannon_pos = None
                if self.player.character==LIRA_KEY: self.player.lira_end_domain(self)
                # Guardiao do Ruan so existe enquanto o Dominio estiver ativo.
                if self.ruan_guardian is not None:
                    self.ruan_guardian.dead = True
                    self.ruan_guardian = None

        # SANTUARIO MALEVOLENTE: barreira aberta, cobre a arena inteira.
        # 5 de dano-base a cada 0,1s; nao crita. Dedos e bonus gerais de dano ainda afetam o Sukuna.
        if self.domain_active and self.player.character == SUKUNA_KEY:
            self.sukuna_domain_tick_cd -= dt
            ticks=0
            while self.sukuna_domain_tick_cd <= 0.0 and ticks < 3:
                self.sukuna_domain_tick_cd += 0.10
                old_kind=self.current_damage_kind; self.current_damage_kind="sukuna_domain"
                for e in list(self.enemies):
                    if e.dead or isinstance(e, GlonkEnemy):
                        continue
                    dmg=5.0*(1.25 if self.player.sukuna_king_curses else 1.0)*self.player.effective_damage_mult(self,e,"sukuna_domain",e.pos.distance_to(self.player.pos))
                    e.damage(dmg,self,self.player.pos,minimal_fx=True)
                self.current_damage_kind=old_kind
                ticks+=1

        # Pequenas orbes de vida aparecem naturalmente, EXCETO no EXTINCAO.
        self.ambient_heal_orb_timer -= dt
        if self.ambient_heal_orb_timer <= 0:
            if self.game_mode != "extinction" and sum(1 for d in self.drops if d.kind == "ambient_heal") < 4:
                px = random.uniform(S(90), W-S(90))
                py = random.uniform(S(235), H-S(385))
                self.drops.append(Drop((px, py), "ambient_heal"))
            self.ambient_heal_orb_timer = random.uniform(6.0, 11.0)

        if self.combo_timer > 0:
            self.combo_timer -= dt
            if self.combo_timer <= 0:
                self.combo = 0

        # Dominio do Kayk: almas atacam automaticamente sem criar dezenas de projeteis.
        # Dano direto periodico deixa a expansao muito mais leve no Android.
        if self.domain_active and self.player.character == "Kayk" and self.player.in_domain(self):
            self.kayk_domain_fire_cd -= dt
            if self.kayk_domain_fire_cd <= 0:
                targets = [e for e in self.enemies if not e.dead and not isinstance(e, GlonkEnemy) and self.is_in_domain(e.pos)]
                targets.sort(key=lambda e: e.pos.distance_to(self.player.pos))
                max_targets = 3 if self.player.kayk_thousand_souls else 2
                old_kind = self.current_damage_kind
                self.current_damage_kind = "soul_shot"
                for target in targets[:max_targets]:
                    dmg_mult = 0.88 if self.player.kayk_thousand_souls else 0.60
                    damage = self.player.base_damage * dmg_mult * self.player.effective_damage_mult(self, target, "soul_shot", target.pos.distance_to(self.player.pos))
                    target.damage(damage, self, self.player.pos)
                    self.damage_texts.append(DamageText("ALMA!", pygame.Vector2(target.pos), PURPLE))
                self.current_damage_kind = old_kind
                base_cd = 0.28 if self.player.kayk_armed_procession else 0.42
                if self.player.domain_evolution:
                    base_cd *= 0.90
                self.kayk_domain_fire_cd = base_cd

        move_dir = self.get_move_dir()
        self.player.update(dt, self, move_dir)
        self.sin_sloth_slow=False
        if self.state != "playing":
            return
        if self.bad_time_active:
            self.update_bad_time(dt)
        self.sans_bones=[b for b in self.sans_bones if b.update(dt,self)]
        for fx in self.sans_blaster_fx:
            fx["timer"]-=dt
        self.sans_blaster_fx=[fx for fx in self.sans_blaster_fx if fx["timer"]>0]
        if self.attack_held and self.player.character not in ("Sans", "Potential Man", HANK_KEY, RIP_INDRA_KEY, HISOKA_KEY) and not self.player.has_divine_attack_hold():
            self.player.attack(self)

        # Atualiza invocacoes da Ana e armas Divinas persistentes.
        self.summons = [summon for summon in self.summons if summon.update(dt, self)]
        self.orbital_anas=[a for a in self.orbital_anas if a.update(dt,self)]
        self.planted_pineapples=[p for p in self.planted_pineapples if p.update(dt,self)]
        if self.divine_burst_fx:
            self.divine_burst_fx["timer"]-=dt
            if self.divine_burst_fx["timer"]<=0: self.divine_burst_fx=None

        # Amigos do Ruan atacam antes dos inimigos; depois podem ser escolhidos como alvo.
        self.servants = [serv for serv in self.servants if serv.update(dt, self)]
        if self.ruan_guardian is not None and self.ruan_guardian.dead:
            self.ruan_guardian = None
        # Vinicius 13: torretas, muros e pedras do Canhao Anti-Tita.
        self.vinicius_turrets=[x for x in self.vinicius_turrets if x.update(dt,self)]
        self.vinicius_walls=[x for x in self.vinicius_walls if x.update(dt,self)]
        self.vinicius_rocks=[x for x in self.vinicius_rocks if x.update(dt,self)]
        if self.player.character=="Vinicius 13" and self.vinicius_scrap>=20 and not any(t.mega and not t.dead for t in self.vinicius_turrets) and self.state=="playing":
            self.open_vinicius_mega_choice()
            if self.state!="playing": return

        # Caes Divinos e Mahoraga. Permanecem entre ondas enquanto estiverem vivos.
        self.potential_summons=[x for x in self.potential_summons if x.update(dt,self)]
        if self.mahoraga is not None and self.mahoraga.dead:
            self.mahoraga=None
            self.mahoraga_hostile_to_dogs=False

        slow_factor = 0.45 if self.enemy_slow_timer > 0 else 1.0
        for e in self.enemies:
            e.update(dt * slow_factor, self)
        self.enemies = [e for e in self.enemies if not e.dead]
        if self.game_mode=="evolution" and self.evolution_traits.count("regeneration")>0:
            regen=0.0035*self.evolution_traits.count("regeneration")*dt
            for e in self.enemies:
                e.hp=min(e.max_hp,e.hp+e.max_hp*regen)

        # Dominios sao moveis: se os circulos se encostarem DEPOIS de ativados,
        # o Clash ainda comeca. Nao depende apenas do instante da ativacao.
        if self.domain_active and not self.domain_clash_active and self.player.character not in ("Sans", "Potential Man"):
            for boss in self.enemies:
                if isinstance(boss, Boss) and boss.domain_active and self.domains_overlap(boss):
                    self.start_domain_clash(boss)
                    break
        self.update_domain_clash(dt)

        # Explosoes atrasadas (Dash Fantasma etc.)
        remaining_blasts = []
        for b in self.delayed_blasts:
            b["timer"] -= dt
            if b["timer"] <= 0:
                self.spawn_particles(b["pos"], b["color"], 22)
                old = self.current_damage_kind
                self.current_damage_kind = "ghost_dash"
                for e in list(self.enemies):
                    if not e.dead and e.pos.distance_to(b["pos"]) <= b["radius"]:
                        e.damage(b["damage"] * self.player.effective_damage_mult(self, e), self, b["pos"])
                self.current_damage_kind = old
                self.shake = max(self.shake, S(12))
            else:
                remaining_blasts.append(b)
        self.delayed_blasts = remaining_blasts

        for fx in getattr(self,"hank_explosions",[]): fx["timer"]-=dt
        self.hank_explosions=[fx for fx in getattr(self,"hank_explosions",[]) if fx["timer"]>0]

        if getattr(self, "hank_artillery_queue", None):
            alive_marks = []
            for mark in self.hank_artillery_queue:
                mark["timer"] -= dt
                if mark["timer"] <= 0 and not mark.get("done", False):
                    mark["done"] = True
                    self.trigger_hank_explosion(mark["pos"],self.player.base_damage*2.8,mark["radius"],artillery=True)
                if mark["timer"] > -0.15:
                    alive_marks.append(mark)
            self.hank_artillery_queue = alive_marks

        new_projectiles = []
        for pr in self.projectiles:
            # Tempo de Caca: abacaxi teleguiado durante a ida.
            if isinstance(pr,BoomerangProjectile) and getattr(pr,"divine_pedro",False) and not pr.returning:
                targets=[e for e in self.enemies if not e.dead and e.id not in pr.hit_ids]
                if targets:
                    target=min(targets,key=lambda e:e.pos.distance_to(pr.pos)); desired=target.pos-pr.pos
                    if desired.length_squared()>0: pr.vel=pr.vel.lerp(desired.normalize()*pr.base_speed,min(1.0,7.5*dt))
            if isinstance(pr,BoomerangProjectile) and getattr(pr,"predator",False) and not pr.returning and pr.hit_ids:
                targets=[e for e in self.enemies if not e.dead and e.id not in pr.hit_ids]
                if targets:
                    target=min(targets,key=lambda e:e.pos.distance_to(pr.pos)); desired=target.pos-pr.pos
                    if desired.length_squared()>0: pr.vel=pr.vel.lerp(desired.normalize()*pr.base_speed,min(1.0,8.0*dt))
            if pr.owner=="player" and getattr(pr,"kind","")=="sans_bone" and self.player.sans_stubborn_bone:
                targets=[e for e in self.enemies if not e.dead and e.id not in pr.hit_ids]
                if targets:
                    target=min(targets,key=lambda e:e.pos.distance_to(pr.pos)); desired=target.pos-pr.pos
                    if desired.length_squared()>0: pr.vel=pr.vel.lerp(desired.normalize()*max(S(520),pr.vel.length()),min(1.0,2.6*dt))

            if pr.owner=="player" and getattr(pr,"kind","")=="hisoka_domain_card":
                target=getattr(pr,"hisoka_target",None)
                if target is not None and not getattr(target,"dead",True):
                    desired=target.pos-pr.pos
                    if desired.length_squared()>0:
                        speed=max(S(760),pr.vel.length()); pr.vel=pr.vel.lerp(desired.normalize()*speed,min(1.0,10.0*dt))

            # Power-up da Strikada: bola teleguiada corrige a rota para o alvo mais proximo.
            if pr.owner == "player" and getattr(pr, "kind", "") == "strikada_ball" and getattr(pr, "strikada_homing", False):
                targets = [e for e in self.enemies if not e.dead and e.id not in pr.hit_ids]
                if targets:
                    target = min(targets, key=lambda e:e.pos.distance_to(pr.pos))
                    desired = target.pos-pr.pos
                    if desired.length_squared() > 0:
                        speed = max(S(420), pr.vel.length())
                        pr.vel = pr.vel.lerp(desired.normalize()*speed, min(1.0, 5.5*dt))

            # Vinicius 13: correcao leve de rota, sem virar teleguiado perfeito.
            if pr.owner == "player" and getattr(pr,"kind","") == "vinicius_bolt":
                targets=[e for e in self.enemies if not e.dead and e.id not in pr.hit_ids]
                if targets:
                    target=min(targets,key=lambda e:e.pos.distance_to(pr.pos)); desired=target.pos-pr.pos
                    if desired.length_squared()>0:
                        speed=max(S(500),pr.vel.length()); pr.vel=pr.vel.lerp(desired.normalize()*speed,min(1.0,2.1*dt))

            # Dominio da Ana: projeteis dentro da area perseguem o alvo mais proximo.
            if pr.owner == "player" and self.player.character == "Ana" and self.domain_active and self.is_in_domain(pr.pos):
                targets = [e for e in self.enemies if not e.dead and self.is_in_domain(e.pos)]
                if targets:
                    target = min(targets, key=lambda e: e.pos.distance_to(pr.pos))
                    desired = target.pos - pr.pos
                    if desired.length_squared() > 0:
                        speed = max(S(260), pr.vel.length())
                        desired = desired.normalize() * speed
                        pr.vel = pr.vel.lerp(desired, min(1.0, 7.0 * dt))
            proj_mult = slow_factor if pr.owner == "enemy" else 1.0
            if pr.owner=="enemy" and self.player.character=="Glonk" and self.player.glonk_professional_coward:
                proj_mult *= 0.75
            # Metavisao do Cadeado Azul: projeteis inimigos perdem muita velocidade dentro da area.
            if (pr.owner == "enemy" and self.player.character == "Strikada Egoísta" and self.domain_active
                    and self.is_in_domain(pr.pos)):
                proj_mult *= 0.45
            proj_dt = dt * proj_mult
            if not pr.update(proj_dt):
                if getattr(pr,"kind","")=="strikada_ball" and self.player.strikada_self_pass:
                    self.player.attack_cd=min(self.player.attack_cd,0.12)
                    self.damage_texts.append(DamageText("PASSE PRA MIM!",pygame.Vector2(self.player.pos),(125,220,255),0.45))
                if isinstance(pr,BoomerangProjectile) and pr.returned_to_player and getattr(pr,"double_crop",False) and random.random()<0.30:
                    d=self.attack_direction() if hasattr(self,"attack_direction") else self.player.facing
                    if d.length_squared()==0: d=pygame.Vector2(1,0)
                    extra=BoomerangProjectile(self.player,d,self.player.base_damage*self.player.projectile_bonus,self.player.pedro_speed_mult,self.player.pedro_range_mult,self.player.pedro_return_hit,self.player.pedro_explosive,self.player.pedro_crown)
                    extra.domain_charge_raw=0.0; extra.domain_charge_uses_left=0; new_projectiles.append(extra)
                    self.damage_texts.append(DamageText("COLHEITA DUPLA!",pygame.Vector2(self.player.pos),YELLOW,0.55))
                if isinstance(pr,BoomerangProjectile) and not pr.hit_any and getattr(pr,"industrial",False):
                    self.delayed_blasts.append({"timer":2.0,"pos":pygame.Vector2(pr.pos),"radius":S(95),"damage":self.player.base_damage*1.10,"color":YELLOW})
                    self.damage_texts.append(DamageText("ABACAXI PLANTADO",pygame.Vector2(pr.pos),YELLOW,0.55))
                if isinstance(pr, BoomerangProjectile) and pr.returned_to_player and (not pr.hit_any or getattr(pr,"divine_pedro",False)):
                    amount=4 if getattr(pr,"divine_pedro",False) else 2
                    self.player.heal(amount, self)
                    self.player.recover_stamina(amount, self)
                    self.damage_texts.append(DamageText(f"+{amount} HP / +{amount} STA", pygame.Vector2(self.player.pos), GREEN, 0.8))
                    if self.mode == "arena" and not is_beta_character(self.player.character):
                        SAVE["pineapple_refunds"] = SAVE.get("pineapple_refunds", 0) + 1
                        if SAVE["pineapple_refunds"] >= 25: self.unlock_achievement("pineapple_25")
                        save_data(SAVE)
                continue

            # Hank: ao atingir 65% do caminho ate a borda, a bala explode mesmo sem acertar alvo.
            if getattr(pr,"kind","")=="hank_shell" and hasattr(pr,"hank_max_distance"):
                range_origin=pygame.Vector2(getattr(pr,"hank_range_origin",getattr(pr,"origin",pr.pos)))
                traveled=pr.pos.distance_to(range_origin)
                if traveled >= pr.hank_max_distance:
                    d=pygame.Vector2(pr.vel)
                    if d.length_squared()>0:
                        d=d.normalize()
                        pr.pos=range_origin+d*pr.hank_max_distance
                    self.trigger_hank_explosion(pr.pos,getattr(pr,"hank_explosion_damage",pr.damage*.85)*(1.50 if getattr(pr,"hank_confirmed_target",False) else 1.0),getattr(pr,"hank_explosion_radius",S(155)),domain_charge_raw=20.0)
                    continue

            # Hitbox das paredes: Pedro/Strikada refletem; todo o resto para na borda.
            if not projectile_arena_wall_collision(pr):
                if getattr(pr,"kind","")=="hank_shell":
                    self.trigger_hank_explosion(pr.pos,getattr(pr,"hank_explosion_damage",pr.damage*.85)*(1.50 if getattr(pr,"hank_confirmed_target",False) else 1.0),getattr(pr,"hank_explosion_radius",S(155)),domain_charge_raw=20.0)
                continue

            if pr.owner == "enemy":
                if self.player.parry_time > 0 and pr.pos.distance_to(self.player.pos) <= S(95):
                    pr.owner = "player"
                    pr.vel *= -1.35
                    pr.damage *= 2.2
                    pr.color = YELLOW
                    pr.parry_reflected = True
                    self.player.recover_stamina(10, self)
                    self.parries += 1
                    # V15: Parry nao recarrega mais Dominio; somente acertos em inimigos.
                    self.record_clash_parry()
                    AUDIO.play("parry", 0.95, 80)
                    self.damage_texts.append(DamageText("PARRY!", pygame.Vector2(self.player.pos), YELLOW))
                    self.shake = max(self.shake, S(9))
                    if "PARADOXO BALISTICO" in self.synergies:
                        self.enemy_slow_timer = max(self.enemy_slow_timer, 1.25)
                    if self.player.character == "Kevyn" and self.player.kevyn_absolute_parry:
                        self.player.kevyn_absolute_parry_ready=True
                        self.damage_texts.append(DamageText("PARRY ABSOLUTO",pygame.Vector2(self.player.pos),YELLOW,0.65))
                    if self.player.character == "Kevyn" and self.player.kevyn_time_counter:
                        old = self.current_damage_kind
                        self.current_damage_kind = "parry_slash"
                        for e in list(self.enemies):
                            if not e.dead and e.pos.distance_to(self.player.pos) <= S(180):
                                e.damage(self.player.base_damage*1.35*self.player.effective_damage_mult(self,e,"sword"), self, self.player.pos)
                        self.current_damage_kind = old
                    new_projectiles.append(pr)
                    continue

                # Amigos/guardiao do Ruan podem interceptar projeteis inimigos.
                intercepted = False
                for serv in list(self.servants):
                    if not serv.dead and pr.pos.distance_to(serv.pos) <= pr.radius + serv.radius:
                        serv.take_damage(pr.damage, self)
                        intercepted = True
                        break
                if not intercepted:
                    for summon in list(self.potential_summons):
                        if not summon.dead and pr.pos.distance_to(summon.pos) <= pr.radius + summon.radius:
                            summon.take_damage(pr.damage,self)
                            intercepted=True
                            break
                if intercepted:
                    continue

                if pr.pos.distance_to(self.player.pos) <= pr.radius + self.player.radius:
                    if self.player.dash_time <= 0:
                        if getattr(pr, "gula_devour", False):
                            self.gula_devour()
                        else:
                            self.player.take_damage(pr.damage, self)
                            if getattr(pr,"kind","") == "rival_vasco_bet":
                                rv = getattr(pr,"rival_vasco_owner",None)
                                if rv is not None and not getattr(rv,"dead",False):
                                    rv.rival_vasco_bet=min(100.0,rv.rival_vasco_bet+2.0)
                    continue
            else:
                hit = False
                strikada_continue = False
                maho = getattr(self, "mahoraga", None)
                if maho is not None and not maho.dead and not getattr(pr, "hit_mahoraga", False):
                    if pr.pos.distance_to(maho.pos) <= pr.radius + maho.radius:
                        source = getattr(pr, "kind", "projectile")
                        origin = getattr(pr, "origin", self.player.pos)
                        dist = maho.pos.distance_to(origin)
                        dmg = pr.damage * self.player.effective_damage_mult(self, None, source, dist)
                        if isinstance(pr, BoomerangProjectile) and pr.returning:
                            dmg *= self.player.pedro_return_damage_mult
                        if isinstance(pr, HisokaCardProjectile) and pr.returning:
                            dmg *= 1.40 if self.player.hisoka_elastic_gum else 1.0
                        if random.random() < self.player.crit_chance:
                            dmg *= self.player.crit_damage_mult
                        charge_raw = self.projectile_domain_charge_value(pr)
                        self.current_domain_charge_raw_override = charge_raw if charge_raw > 0 else None
                        maho.take_damage(dmg, self, pr.pos, from_player=True)
                        self.current_domain_charge_raw_override = None
                        if source == "hank_shell":
                            self.trigger_hank_explosion(maho.pos,getattr(pr,"hank_explosion_damage",pr.damage*.85),getattr(pr,"hank_explosion_radius",S(155)),exclude=maho)
                        if source == "vasco_bet" and self.player.character == "Vasco":
                            self.player.vasco_bet_level = min(100.0, self.player.vasco_bet_level + 2.0)
                            if self.domain_active and self.player.vasco_bet_level >= 100.0 and self.player.vasco_jackpot_timer <= 0:
                                self.player.vasco_start_jackpot(self)
                        pr.hit_mahoraga = True
                        self.player.recover_stamina(self.player.stamina_on_hit, self)
                        self.register_combo_hit()
                        if not isinstance(pr, (BoomerangProjectile, HisokaCardProjectile)):
                            if pr.pierce > 0:
                                pr.pierce -= 1
                            else:
                                hit = True
                if hit:
                    continue
                for e in list(self.enemies):
                    if e.id in pr.hit_ids or e.dead:
                        continue
                    if pr.pos.distance_to(e.pos) <= pr.radius + e.radius:
                        source = getattr(pr, "kind", "projectile")
                        origin = getattr(pr, "origin", self.player.pos)
                        dist = e.pos.distance_to(origin)
                        dmg = pr.damage * self.player.effective_damage_mult(self, e, source, dist)
                        if isinstance(pr, BoomerangProjectile):
                            pr.hit_any = True
                            if pr.returning:
                                dmg *= self.player.pedro_return_damage_mult
                        if isinstance(pr, HisokaCardProjectile) and pr.returning:
                            dmg *= (1.40 if self.player.hisoka_elastic_gum else 1.0) * getattr(pr,"return_mult",1.0)
                        if isinstance(pr, BoomerangProjectile) and pr.returning and pr.crown:
                            dmg *= 1.65
                            self.damage_texts.append(DamageText("COROA!", pygame.Vector2(e.pos), YELLOW))
                        passive_crit_hit = random.random() < self.player.crit_chance
                        if passive_crit_hit:
                            dmg *= self.player.crit_damage_mult
                            self.damage_texts.append(DamageText("CRIT!", pygame.Vector2(e.pos), YELLOW))
                        self.current_damage_kind = source
                        if source=="strikada_ball":
                            self.strikada_current_bounces=getattr(pr,"strikada_bounce_count",0)
                        was_alive_before_hit = not e.dead
                        charge_raw = self.projectile_domain_charge_value(pr)
                        self.current_domain_charge_raw_override = charge_raw if charge_raw > 0 else None
                        e.damage(dmg, self, pr.pos)
                        self.current_domain_charge_raw_override = None
                        if source == "hank_shell":
                            self.trigger_hank_explosion(e.pos,getattr(pr,"hank_explosion_damage",pr.damage*.85),getattr(pr,"hank_explosion_radius",S(155)),exclude=e)
                        if passive_crit_hit and was_alive_before_hit and e.dead:
                            self.award_passive_critical_kill(e)
                        if source == "vasco_bet" and self.player.character == "Vasco":
                            old_bet = self.player.vasco_bet_level
                            self.player.vasco_bet_level = min(100.0, self.player.vasco_bet_level + 2.0)
                            gained = int(self.player.vasco_bet_level-old_bet)
                            if gained > 0:
                                self.damage_texts.append(DamageText(f"APOSTA +{gained}", pygame.Vector2(e.pos), VASCO_NEON, 0.45))
                            if self.domain_active and self.player.vasco_bet_level >= 100.0 and self.player.vasco_jackpot_timer <= 0:
                                self.player.vasco_start_jackpot(self)
                        if source=="lira_censor" and not e.dead and not isinstance(e,Boss):
                            e.apply_lira_censor(random.choice(["strength","speed","resistance","intelligence"]),0.30 if self.player.lira_thick_bar else 0.20,self)
                        if source=="hisoka_charged_card" and not e.dead:
                            e.hisoka_stun_timer=max(getattr(e,"hisoka_stun_timer",0.0),getattr(pr,"hisoka_stun",1.0))
                            self.damage_texts.append(DamageText("PARALISADO!",pygame.Vector2(e.pos),HISOKA_COLOR,0.65))
                        if source=="hisoka_spider_card" and isinstance(pr,HisokaCardProjectile) and pr.returning and not e.dead:
                            toward=self.player.pos-e.pos
                            if toward.length_squared()>0:
                                dist=toward.length(); e.pos += toward.normalize()*max(0.0,min(S(180),dist-S(95)))
                        if source=="rip_wave" and getattr(pr,"rip_explosive",False):
                            oldk=self.current_damage_kind; self.current_damage_kind="rip_wave_explosion"
                            radius=S(205)*(1.20 if "PERMISSAO DE ADMIN" in self.synergies else 1.0)
                            for other in list(self.enemies):
                                if other is not e and not other.dead and other.pos.distance_to(e.pos)<=radius:
                                    other.damage(pr.damage*0.65*self.player.effective_damage_mult(self,other,"rip_wave_explosion",other.pos.distance_to(self.player.pos)),self,e.pos,minimal_fx=True)
                            self.current_damage_kind=oldk; self.spawn_particles(e.pos,ORANGE,20); self.shake=max(self.shake,S(10))
                        if source == "dual_pistol" and getattr(pr, "forge_kayk", False):
                            e.forge_slow_timer = max(getattr(e,"forge_slow_timer",0.0), 2.8)
                            old_kind = self.current_damage_kind; self.current_damage_kind="forge_kayk_explosion"
                            for other in list(self.enemies):
                                if other is not e and not other.dead and other.pos.distance_to(e.pos) <= S(105):
                                    other.forge_slow_timer=max(getattr(other,"forge_slow_timer",0.0),1.8)
                                    other.damage(pr.damage*0.38, self, e.pos, minimal_fx=True)
                            self.current_damage_kind=old_kind
                            self.spawn_particles(e.pos,PURPLE,6)
                        killed_by_this_hit = was_alive_before_hit and e.dead
                        if source=="strikada_ball":
                            pr.strikada_bounce_count=getattr(pr,"strikada_bounce_count",0)+1
                            if killed_by_this_hit:
                                pr.strikada_kills=getattr(pr,"strikada_kills",0)+1
                                if self.player.strikada_impossible_goal and pr.strikada_kills>=3:
                                    self.player.strikada_next_infinite=True
                        double_chance = getattr(pr, "double_hit_chance", 0.0)
                        if self.player.character == "Ana" and self.domain_active and self.is_in_domain(e.pos) and self.player.domain_evolution:
                            double_chance = max(double_chance, 0.25)
                        if self.player.character == "Ana" and self.player.ana_reality_exe and self.domain_active and self.is_in_domain(e.pos):
                            double_chance = max(double_chance, 0.45)
                        if random.random() < double_chance:
                            e.damage(dmg, self, pr.pos)
                            self.damage_texts.append(DamageText("ERRO x2", pygame.Vector2(e.pos), PINK))
                        self.current_damage_kind = None
                        if source=="strikada_ball": self.strikada_current_bounces=0
                        pr.hit_ids.add(e.id)
                        self.player.recover_stamina(self.player.stamina_on_hit, self)
                        if source == "shotgun" and self.player.ycaro_aggressive_reload:
                            self.player.recover_stamina(0.75, self)
                        self.register_combo_hit()

                        # Vinicius 13: primeiro impacto espalha ate 3 tiros para alvos proximos.
                        if source == "vinicius_bolt" and not getattr(pr,"vinicius_child",False):
                            options=[o for o in self.enemies if not o.dead and o is not e and o.id not in pr.hit_ids and o.pos.distance_to(e.pos)<=S(390)]
                            options.sort(key=lambda o:o.pos.distance_to(e.pos))
                            for other in options[:3]:
                                d=other.pos-e.pos
                                if d.length_squared()>0:
                                    child=Projectile(e.pos+d.normalize()*S(18),d.normalize()*S(690),pr.damage*0.72,"player",S(7),RED,1.55,0); child.kind="vinicius_bolt"; child.origin=pygame.Vector2(e.pos); child.vinicius_child=True; child.hit_ids.add(e.id); child.domain_charge_raw=0.0; child.domain_charge_uses_left=0; new_projectiles.append(child)

                        # Abacaxi Explosivo do Pedro: splash sem consumir o bumerangue.
                        if isinstance(pr, BoomerangProjectile) and pr.explosive:
                            old_kind = self.current_damage_kind
                            self.current_damage_kind = "pineapple_explosion"
                            for other in list(self.enemies):
                                if other is not e and not other.dead and other.pos.distance_to(e.pos) <= S(125):
                                    other.damage(pr.damage*0.48*self.player.pedro_damage_mult, self, e.pos)
                            self.current_damage_kind = old_kind
                            self.spawn_particles(e.pos, YELLOW, 10)

                        # Parry Explosivo / Paradoxo Balistico
                        if getattr(pr, "parry_reflected", False) and self.player.explosive_parry:
                            old = self.current_damage_kind
                            self.current_damage_kind = "parry_explosion"
                            for other in list(self.enemies):
                                if not other.dead and other is not e and other.pos.distance_to(e.pos) <= S(145):
                                    other.damage(pr.damage*0.75, self, e.pos)
                            self.current_damage_kind = old

                        # Strikada Egoista: cada acerto escolhe o proximo inimigo. No Dominio,
                        # o limite deixa de existir e a bola pode revisitar alvos depois de completar o ciclo.
                        if source == "strikada_ball":
                            if getattr(pr, "strikada_kill_explosion", False) and killed_by_this_hit:
                                old_kind = self.current_damage_kind
                                self.current_damage_kind = "strikada_goal_explosion"
                                for other in list(self.enemies):
                                    if other is not e and not other.dead and other.pos.distance_to(e.pos) <= S(145):
                                        other.damage(pr.damage*0.62, self, e.pos)
                                self.current_damage_kind = old_kind
                                self.spawn_particles(e.pos, (125,220,255), 10)
                            infinite = (self.domain_active and self.player.character == "Strikada Egoísta" and self.is_in_domain(e.pos)) or getattr(pr,"strikada_force_infinite",False)
                            if not infinite:
                                pr.strikada_hits_left = max(0, getattr(pr, "strikada_hits_left", 4)-1)
                            # Quando todos os alvos ja foram tocados no Dominio, libera uma nova volta.
                            options = [o for o in self.enemies if not o.dead and o.id not in pr.hit_ids and o is not e]
                            if infinite and not options:
                                pr.hit_ids = {e.id}
                                options = [o for o in self.enemies if not o.dead and o is not e]
                            can_continue = infinite or getattr(pr, "strikada_hits_left", 0) > 0
                            if can_continue and options:
                                target = min(options, key=(lambda o:o.hp/max(1,o.max_hp)) if self.player.strikada_metavision else (lambda o:o.pos.distance_to(e.pos)))
                                d = target.pos-e.pos
                                if d.length_squared() > 0:
                                    speed = max(S(620), pr.vel.length())
                                    pr.vel = d.normalize()*speed
                                    pr.pos = pygame.Vector2(e.pos) + d.normalize()*S(18)
                                    pr.life = max(pr.life, 1.8 if not infinite else 4.0)
                                    strikada_continue = True
                                    break
                            # Sem proximo alvo ou limite encerrado: a bola desaparece neste impacto.
                            hit = True
                            break

                        # Ricochete: nasce um novo projetil em direcao a outro alvo.
                        chance = self.player.ricochet_chance
                        if chance > 0 and not getattr(pr, "ricocheted", False) and random.random() < chance:
                            options = [o for o in self.enemies if not o.dead and o is not e]
                            if options:
                                target = min(options, key=lambda o:o.pos.distance_to(e.pos))
                                d = target.pos-e.pos
                                if d.length_squared()>0:
                                    d=d.normalize()
                                    rp=Projectile(e.pos, d*max(S(520),pr.vel.length()), pr.damage*0.78, "player", pr.radius, pr.color, 1.4, 0)
                                    rp.kind=source
                                    rp.ricocheted=True
                                    rp.hit_ids.add(e.id)
                                    rp.domain_charge_raw=0.0; rp.domain_charge_uses_left=0
                                    rp.double_hit_chance=getattr(pr,"double_hit_chance",0.0)
                                    new_projectiles.append(rp)

                        if isinstance(pr, (BoomerangProjectile, HisokaCardProjectile)):
                            # Bumerangues e cartas do Hisoka continuam o caminho e depois retornam.
                            pass
                        elif pr.pierce > 0:
                            pr.pierce -= 1
                        else:
                            hit = True
                            break
                if strikada_continue:
                    new_projectiles.append(pr)
                    continue
                if hit:
                    continue
            new_projectiles.append(pr)
        self.projectiles = new_projectiles

        alive_drops = []
        for d in self.drops:
            if not d.update(dt):
                continue
            dist = d.pos.distance_to(self.player.pos)
            if self.player.orb_magnet and dist < S(470) and dist > 1:
                d.pos += (self.player.pos-d.pos).normalize() * S(520) * dt
                dist = d.pos.distance_to(self.player.pos)
            pickup_radius=d.radius + self.player.radius + S(8)
            if d.kind in ("coin","heal","ambient_heal","friend_heal"):
                pickup_radius *= 1.0 + getattr(self.player,"passive_collect_bonus",0.0)
            if dist <= pickup_radius:
                if str(d.kind).startswith("mat:"):
                    self.collect_forge_material(d.kind.split(":",1)[1],1)
                    continue
                if d.kind == "heal":
                    if self.game_mode == "extinction":
                        self.damage_texts.append(DamageText("EXTINCAO: SEM CURA", pygame.Vector2(self.player.pos), RED, 0.7))
                    else:
                        AUDIO.play("heal", 0.82, 60)
                        if self.player.insatiable_hunger:
                            self.damage_texts.append(DamageText("FOME", pygame.Vector2(self.player.pos), RED))
                        else:
                            self.player.heal(max(22, self.player.max_hp * 0.18), self)
                        if self.player.questionable_hemo:
                            self.player.recover_stamina(max(12, self.player.max_stamina*0.12), self)
                elif d.kind == "ambient_heal":
                    AUDIO.play("heal", 0.55, 80)
                    if not self.player.insatiable_hunger:
                        self.player.heal(max(6, self.player.max_hp * 0.06), self)
                elif d.kind == "friend_heal":
                    AUDIO.play("heal",0.45,80)
                    if not self.player.insatiable_hunger: self.player.heal(5,self)
                elif d.kind == "stamina":
                    AUDIO.play("stamina", 0.82, 60)
                    self.player.recover_stamina(max(28, self.player.max_stamina * 0.25), self)
                elif d.kind == "shield": AUDIO.play("pickup", 0.70, 50); self.player.shield += 1
                elif d.kind == "haste": AUDIO.play("pickup", 0.70, 50); self.player.speed_buff = 8
                elif d.kind == "coin":
                    AUDIO.play("pickup", 0.62, 45)
                    reward_mult=difficulty_cfg(getattr(self,"difficulty","easy"))["reward"] if self.mode=="arena" else 1.0
                    self.run_coins += max(1,int(8 * self.coin_multiplier * reward_mult * max(0.10,1.0+self.player.passive_coin_bonus)))
                self.spawn_particles(d.pos, Drop.COLORS[d.kind], 9)
                if self.player.orb_magnet and d.kind in ("heal","ambient_heal","friend_heal","stamina"):
                    self.orb_chain_count += 1
                    self.orb_chain_timer = 2.0
                    if self.orb_chain_count >= 3:
                        self.orb_chain_count = 0
                        old = self.current_damage_kind
                        self.current_damage_kind = "orb_blast"
                        for e in list(self.enemies):
                            if not e.dead and e.pos.distance_to(self.player.pos) <= S(250):
                                e.damage(self.player.base_damage*1.8*self.player.damage_mult, self, self.player.pos)
                        self.current_damage_kind = old
                        self.damage_texts.append(DamageText("COLAPSO DE ORBES!", pygame.Vector2(self.player.pos), PURPLE))
                continue
            alive_drops.append(d)
        self.drops = alive_drops

        self.particles = [p for p in self.particles if p.update(dt)]
        self.damage_texts = [d for d in self.damage_texts if d.update(dt)]
        self.forge_fire_trails = [f for f in self.forge_fire_trails if f.update(dt, self)]

        if self.parries >= 100:
            self.unlock_achievement("parry_100")
        if self.perfect_dodges >= 75:
            self.unlock_achievement("dodge_75")

        if self.mode == "afk":
            self.player.hp = min(self.player.max_hp, self.player.hp + self.player.max_hp * 0.08 * dt)
            cap = self.player.max_stamina * (1.30 if self.player.beyond_limit else 1.0)
            afk_sta_regen = 18.0 * (0.20 if self.player.character == "Sans" and self.bad_time_active else 1.0)
            self.player.stamina = min(cap, self.player.stamina + afk_sta_regen * dt)
            if not any(isinstance(e, TrainingDummy) for e in self.enemies): self.spawn_training_dummy()
        elif self.mode == "training":
            self.player.hp=min(self.player.max_hp,self.player.hp+self.player.max_hp*0.05*dt)
            if not self.enemies:
                self.training_respawn_timer-=dt
                if self.training_respawn_timer<=0:
                    self.spawn_bestiary_target(self.training_target_name); self.training_respawn_timer=1.5
        elif self.game_mode=="arena_survival":
            self.update_arena_survival(dt)
        elif not self.enemies and not self.wave_clear_lock and self.state == "playing":
            self.wave_clear_lock = True
            if self.mahoraga is not None and not self.mahoraga.dead:
                self.mahoraga.end_wave_adapt(self)
            if hasattr(self.player, "vasco_wave_clear"):
                self.player.vasco_wave_clear(self)
            if self.game_mode!="extinction": self.player.heal(10, self)
            self.player.recover_stamina(18, self)
            AUDIO.play("wave_clear", 0.85)
            self.check_special_character_unlocks_on_wave_clear()
            self.player.passive_on_wave_clear(self)
            self.roll_evolution_point()
            # Modo EVOLUCAO: inimigos ganham uma nova propriedade ANTES da proxima wave.
            if self.game_mode=="evolution": self.add_evolution_trait()
            # BOSS RUSH herda um fragmento mecanico do boss anterior.
            if self.game_mode=="boss_rush":
                inherit=["FRENESI","CARAPACA","CERCO","RITUAL","FOME","ECO","PRESSAO"]
                self.boss_heritages.append(inherit[(self.wave-1)%len(inherit)])
                if self.wave>=self.boss_rush_sequence_length():
                    self.complete_mode("BOSS RUSH COMPLETO",f"HERANCAS ACUMULADAS: {len(self.boss_heritages)}"); return
            if self.game_mode=="one_vs_all" and self.wave>=len(self.one_vs_all_roster):
                self.unlock_achievement("solo_survivor")
                self.complete_mode("SOBROU SO VOCE",f"TODOS OS {len(self.one_vs_all_roster)} RIVAIS CAIRAM"); return
            if self.game_mode=="infinite" and self.wave%10==0:
                self.open_curse_choice()
            else:
                self.open_upgrade()

    def update(self, dt):
        self.evolution_notice_timer = max(0.0, self.evolution_notice_timer - dt)
        self.passive_roll_anim=max(0.0,getattr(self,"passive_roll_anim",0.0)-dt)
        self.update_passive_roll_system(dt)
        if self.state == "playing":
            self.update_playing(dt)
        elif self.state in ("menu", "mode_select", "character_select", "difficulty_select", "curse_choice", "mode_complete", "shop", "upgrade", "death", "glonk_death", "upgrade_catalog", "passive_catalog", "passive_roll", "passive_auto_config", "passive_dev", "bestiary", "forge", "items", "weapons", "control_editor", "run_upgrades", "whats_new", "achievements", "missions", "cheats", "vinicius_mega"):
            if self.state=="whats_new": self.update_whats_new_scroll(dt)
            self.particles = [p for p in self.particles if p.update(dt)]
            self.damage_texts = [d for d in self.damage_texts if d.update(dt)]
        AUDIO.sync_music(self)

    def draw_bg(self):
        SCREEN.fill((7, 13, 34) if self.bad_time_active else BG)
        grid = S(80)
        map_top = S(165)
        map_bottom = H - S(335)
        for x in range(0, W, grid):
            pygame.draw.line(SCREEN, (15, 42, 74) if self.bad_time_active else (24, 26, 34), (x, map_top), (x, map_bottom), 1)
        for y in range(map_top, map_bottom, grid):
            pygame.draw.line(SCREEN, (15, 42, 74) if self.bad_time_active else (24, 26, 34), (0, y), (W, y), 1)

        # V8: borda branca mostrando claramente o limite da arena.
        inset = max(2, S(4))
        arena_rect = pygame.Rect(inset, map_top, W - inset * 2, map_bottom - map_top)
        pygame.draw.rect(SCREEN, WHITE, arena_rect, width=max(2, S(5)))

    def camera_offset(self):
        if self.shake <= 0:
            return pygame.Vector2()
        self.shake *= 0.82
        if self.shake < 0.5:
            self.shake = 0
        return pygame.Vector2(random.uniform(-self.shake, self.shake), random.uniform(-self.shake, self.shake))

    def draw_domain_zone(self, offset):
        # V10: apenas contornos leves. Sem superficies alpha gigantes = amigo do Android.
        if self.domain_active and self.player.character not in ("Sans", "Potential Man"):
            if self.player.character == SUKUNA_KEY:
                arena=pygame.Rect(S(4),S(165),W-S(8),max(S(40),H-S(500)))
                pygame.draw.rect(SCREEN,SUKUNA_SLASH,arena,max(2,S(7)))
                pygame.draw.rect(SCREEN,WHITE,arena.inflate(-S(14),-S(14)),max(1,S(2)))
            else:
                c = self.domain_center + offset
                pygame.draw.circle(SCREEN, self.player.color, (int(c.x), int(c.y)), int(self.domain_radius), max(2, S(6)))
                pygame.draw.circle(SCREEN, WHITE, (int(c.x), int(c.y)), max(1, int(self.domain_radius-S(10))), max(1, S(2)))
        for e in self.enemies:
            if isinstance(e, Boss) and not e.dead and e.domain_active:
                c = e.domain_center + offset
                pygame.draw.circle(SCREEN, e.color, (int(c.x), int(c.y)), int(e.domain_radius), max(2, S(7)))
                pygame.draw.circle(SCREEN, RED, (int(c.x), int(c.y)), max(1, int(e.domain_radius-S(12))), max(1, S(2)))

    def draw_domain_cutscene(self):
        # Apenas texto curto: muito mais leve que criar superficies alpha gigantes por frame.
        if self.domain_message_timer <= 0:
            return
        title = "BAD TIME" if self.player.character == "Sans" else ("ULT: INVOCACAO" if self.player.character == "Potential Man" else "EXPANSAO DE DOMINIO")
        draw_text(title, FONT_L, WHITE, (W/2, H*0.25), True)
        draw_text(self.domain_name, FONT_M, CYAN if self.player.character == "Sans" else self.player.color, (W/2, H*0.31), True)
        draw_text(CHARACTER_CONFIG[self.player.character]["domain_desc"], FONT_S, GRAY, (W/2, H*0.355), True)

    def draw_hud(self):
        p = self.player
        x = S(35)
        bw = min(S(900), int(W * 0.39))
        bh = S(34)

        # HP
        y = S(30)
        pygame.draw.rect(SCREEN, DARK, (x, y, bw, bh), border_radius=S(12))
        hp_ratio = clamp(p.hp / max(1, p.max_hp), 0, 1)
        pygame.draw.rect(SCREEN, RED, (x, y, bw*hp_ratio, bh), border_radius=S(12))
        draw_text(f"HP {int(p.hp)}/{int(p.max_hp)}", FONT_S, WHITE, (x+bw/2, y+bh/2), True)

        # Estamina
        sy = y + bh + S(12)
        pygame.draw.rect(SCREEN, DARK, (x, sy, bw, bh), border_radius=S(12))
        st_ratio = clamp(p.stamina / max(1, p.max_stamina), 0, 1)
        pygame.draw.rect(SCREEN, CYAN, (x, sy, bw*st_ratio, bh), border_radius=S(12))
        draw_text(f"ESTAMINA {int(p.stamina)}/{int(p.max_stamina)}", FONT_S, WHITE, (x+bw/2, sy+bh/2), True)

        char_hud = "Vasco, O Apostador Incansável" if p.character == "Vasco" else p.character
        draw_text(f"{char_hud} | {p.weapon_name}", FONT_S, p.color, (x, sy+S(48)))
        if self.mode == "afk":
            draw_text("ZONA AFK", FONT_M, CYAN, (x, sy+S(82)))
        elif self.mode == "training":
            draw_text("TREINO: "+str(self.training_target_name), FONT_M, CYAN, (x, sy+S(82)))
        else:
            draw_text(f"ONDA {self.wave}", FONT_M, WHITE, (x, sy+S(82)))
            dcfg = difficulty_cfg(getattr(self,"difficulty","easy"))
            draw_text(dcfg["name"], FONT_S, dcfg["color"], (x+S(245), sy+S(92)))
            gm=GAME_MODES.get(getattr(self,"game_mode","normal"),GAME_MODES["normal"])
            draw_text(gm["name"],FONT_S,gm["color"],(x+S(390),sy+S(92)))
        draw_text(f"KOs {self.kills}   $ {self.run_coins}", FONT_S, GRAY, (x, sy+S(130)))

        if self.combo > 0:
            draw_text(f"COMBO x{1 + self.combo*0.08:.1f}", FONT_M, YELLOW, (W/2, S(86)), True)

        # Expansao de Dominio no topo direito
        uw = min(S(700), int(W * 0.31))
        ux, uy, uh = W-SAFE-uw, S(35), S(28)
        pygame.draw.rect(SCREEN, DARK, (ux, uy, uw, uh), border_radius=S(10))
        if p.character in ("Glonk", "Glonk 100% Power", "Vinicius 13"):
            label="AUTOMACAO: SEM DOMINIO" if p.character=="Vinicius 13" else "DOMINIO: indisponivel"
            draw_text(label, FONT_S, GRAY, (ux, uy+S(42)))
        elif p.character == "Potential Man":
            alive_maho=self.mahoraga is not None and not self.mahoraga.dead
            if alive_maho:
                ratio=clamp(self.mahoraga.hp/max(1,self.mahoraga.max_hp),0,1)
                pygame.draw.rect(SCREEN,YELLOW,(ux,uy,uw*ratio,uh),border_radius=S(10))
                draw_text(f"MAHORAGA ATIVO | ADAPTACAO {int(self.mahoraga.resistance*100)}%",FONT_S,WHITE,(ux,uy+S(42)))
            else:
                pygame.draw.rect(SCREEN,PURPLE,(ux,uy,uw*(self.domain_charge/100),uh),border_radius=S(10))
                draw_text(f"MAHORAGA {int(self.domain_charge)}%",FONT_S,WHITE,(ux,uy+S(42)))
            dogs=sum(1 for x in self.potential_summons if isinstance(x,DivineDog) and not x.dead)
            dogtxt=f"CAES: {dogs}/2" if dogs else ("CAES: PRONTOS" if p.potential_dog_cd<=0 else f"CAES: {p.potential_dog_cd:.1f}s")
            draw_text(dogtxt,FONT_S,WHITE,(ux,uy+S(76)))
        elif p.character == "Sans":
            ready = self.domain_charge >= 100 or p.stamina < p.max_stamina*0.50
            if self.bad_time_active:
                ratio=clamp(self.domain_timer/max(0.01,self.domain_duration),0,1)
                pygame.draw.rect(SCREEN,CYAN,(ux,uy,uw*ratio,uh),border_radius=S(10))
                draw_text(f"BAD TIME ATIVA {self.domain_timer:.1f}s",FONT_S,WHITE,(ux,uy+S(42)))
            else:
                pygame.draw.rect(SCREEN,CYAN if ready else PURPLE,(ux,uy,uw*(self.domain_charge/100),uh),border_radius=S(10))
                draw_text("BAD TIME PRONTA" if ready else f"BAD TIME {int(self.domain_charge)}% | libera abaixo de 50% STA",FONT_S,WHITE,(ux,uy+S(42)))
            cd_txt="PRONTO" if p.sans_blaster_cd<=0 else f"{p.sans_blaster_cd:.1f}s"
            draw_text(f"BLASTER: {cd_txt}",FONT_S,CYAN,(ux,uy+S(76)))
        elif p.character == "Vasco" and p.vasco_jackpot_timer > 0:
            ratio = clamp(p.vasco_jackpot_timer / max(0.01, p.vasco_jackpot_duration), 0, 1)
            pygame.draw.rect(SCREEN, VASCO_NEON, (ux, uy, uw*ratio, uh), border_radius=S(10))
            draw_text(f"JACKPOT MODE {p.vasco_jackpot_timer:.1f}s | DOMINIO TRAVADO", FONT_S, WHITE, (ux, uy+S(42)))
        elif self.domain_active:
            ratio = clamp(self.domain_timer / max(0.01, self.domain_duration), 0, 1)
            pygame.draw.rect(SCREEN, p.color, (ux, uy, uw*ratio, uh), border_radius=S(10))
            draw_text(f"DOMINIO ATIVO {self.domain_timer:.1f}s - {p.domain_name}", FONT_S, WHITE, (ux, uy+S(42)))
        else:
            pygame.draw.rect(SCREEN, PURPLE, (ux, uy, uw*(self.domain_charge/100), uh), border_radius=S(10))
            draw_text(f"DOMINIO {int(self.domain_charge)}% - {p.domain_name}", FONT_S, WHITE, (ux, uy+S(42)))

        # V13: painel padrao de cooldowns no canto. Novas habilidades devem sempre aparecer aqui.
        cool_x=ux; cool_y=uy+S(104); cool_w=uw
        def _cd(v): return "PRONTO" if v<=0.01 else f"{v:.1f}s"
        parry_label="BLAST" if p.character=="Sans" else "PARRY"
        parry_val=p.sans_blaster_cd if p.character=="Sans" else p.parry_cd
        draw_text(f"ATK {_cd(p.attack_cd)}  |  DASH {_cd(p.dash_cd)}  |  {parry_label} {_cd(parry_val)}",FONT_S,GRAY,(cool_x,cool_y))
        special_text=""; special_color=DIVINE_BLUE
        if p.divine_ana:
            if self.attack_held:
                remain=max(0.0,p.longinus_next_threshold-p.divine_attack_hold)
                special_text=f"LONGINUS: PROXIMA ANA {remain:.1f}s"
            else:
                special_text="LONGINUS: SEGURE ATK 2.0s"
        elif p.divine_kayk:
            used=p.kayk_builder_wave_used==self.wave
            if self.dash_held and not used: special_text=f"BIG BUILDER: {max(0,1-p.divine_dash_hold):.1f}s"
            else: special_text="BIG BUILDER: USADO" if used else "BIG BUILDER: SEGURE DASH 1.0s"
        elif p.divine_ruan:
            if self.dash_held: special_text=f"MANTO: TELEPORTE {max(0,1-p.divine_dash_hold):.1f}s"
            else: special_text="MANTO: DASH=AMIGO SE SOZINHO | SEGURE 1.0s"
        elif p.divine_kevyn:
            special_text=(f"SETE FACES: ATRAIR {max(0,1-p.divine_dash_hold):.1f}s" if self.dash_held else "SETE FACES: SEGURE DASH 1s = ATRAIR | ATK=SPAM | PARRY 1s | DOM 3s")
        elif p.divine_pedro:
            special_text=f"TEMPO DE CACA: SEGURE DASH {max(0,1-p.divine_dash_hold):.1f}s" if self.dash_held else "TEMPO DE CACA: SEGURE DASH 1.0s"
        elif p.divine_vasco:
            special_text=f"LEME DE DHARMA BETA: -{int(p.vasco_dharma_reduction*100)}% DANO RECEBIDO"
        elif p.character==SUKUNA_KEY:
            if self.domain_held:
                special_text=f"SANTUARIO: SEGURE {max(0,3-p.sukuna_domain_hold):.1f}s"
                special_color=SUKUNA_SLASH
            elif self.sukuna_ult_marked:
                special_text="FUUGA MARCADO: TOQUE ULT = DISPARAR | SEGURE 3s = SANTUARIO"
                special_color=SUKUNA_FIRE
            else:
                special_text="TOQUE ULT = MARCAR FUUGA | SEGURE 3s = SANTUARIO"
                special_color=SUKUNA_FIRE
        elif p.character=="Vinicius 13":
            minis=sum(1 for t in self.vinicius_turrets if not t.dead and not t.mega); megas=[t for t in self.vinicius_turrets if t.mega and not t.dead]
            if megas:
                mt=megas[0]; special_text=f"SUCATA {self.vinicius_scrap}/20 | MINI {minis}/5 | {ViniciusTurret.LABELS.get(mt.kind,'MEGA')} {_cd(mt.cd)}"
            else:
                special_text=f"SUCATA {self.vinicius_scrap}/20 | MINI {minis}/5 | MEGA AGUARDANDO"
        if special_text:
            draw_text(special_text,FONT_S,special_color,(cool_x,cool_y+S(30)))

        if p.character == "Vasco":
            bet_y = uy + S(174)
            bet_h = S(24)
            pygame.draw.rect(SCREEN, DARK, (ux,bet_y,uw,bet_h), border_radius=S(9))
            ratio = clamp(p.vasco_bet_level/100.0,0,1)
            if p.vasco_bet_level < 25: bet_color=RED
            elif p.vasco_bet_level < 50: bet_color=ORANGE
            elif p.vasco_bet_level < 75: bet_color=YELLOW
            elif p.vasco_bet_level < 100: bet_color=GREEN
            else: bet_color=VASCO_NEON
            pygame.draw.rect(SCREEN, bet_color, (ux,bet_y,uw*ratio,bet_h), border_radius=S(9))
            draw_text(f"NIVEL DA APOSTA {int(p.vasco_bet_level)}% | DANO x{p.vasco_damage_multiplier():.2f}", FONT_S, WHITE, (ux,bet_y+S(40)))

        if p.character==LIRA_KEY:
            ly=uy+S(174)
            if self.domain_active and p.lira_domain_buffs:
                lm={"strength":"FORCA+70%","life":"HP+50%","resistance":"DEFESA+","speed":"VEL+50%","intelligence":"CD/ALCANCE+"}
                draw_text("C#NSUR# ATIVA: "+" | ".join(lm[k] for k in self.lira_domain_selected if k in p.lira_domain_buffs),FONT_S,LIRA_ACCENT,(ux,ly))
            else:
                draw_text("CENSURA: FORCA / VELOCIDADE / RESISTENCIA / INTELIGENCIA",FONT_S,LIRA_ACCENT,(ux,ly))
        if p.character==SUKUNA_KEY:
            fy=uy+S(174); fh=S(22); gap=max(1,S(2)); seg_w=max(2,(uw-gap*19)/20)
            for i in range(20):
                x=ux+i*(seg_w+gap)
                pygame.draw.rect(SCREEN,SUKUNA_HAIR if i<p.sukuna_fingers else PANEL2,(x,fy,seg_w,fh),border_radius=max(1,S(3)))
            draw_text(f"DEDOS DO SUKUNA {p.sukuna_fingers}/20 | DANO x{p.sukuna_finger_damage_multiplier():.1f} | HP +{p.sukuna_fingers*5}%",FONT_S,WHITE,(ux,fy+S(36)))

        if self.event_name:
            draw_text("EVENTO: " + self.event_name, FONT_S, PINK, (W/2, S(165)), True)

        if self.achievement_timer > 0:
            r = pygame.Rect(W/2-S(250), S(205), S(500), S(70))
            pygame.draw.rect(SCREEN, PANEL2, r, border_radius=S(18))
            draw_text("CONQUISTA: " + self.achievement, FONT_S, YELLOW, r.center, True)

    def draw_controls(self):
        # Joystick analogico: base + knob acompanha o dedo.
        joy = self.buttons["joystick"]
        center = pygame.Vector2(joy.center)
        base_r = min(joy.w, joy.h)//2
        knob_r = max(S(34), int(base_r*0.38))
        knob = center + self.joystick_vector * (base_r-knob_r-S(6))
        pygame.draw.circle(SCREEN, PANEL2, (int(center.x), int(center.y)), base_r)
        pygame.draw.circle(SCREEN, WHITE, (int(center.x), int(center.y)), base_r, max(2,S(4)))
        pygame.draw.circle(SCREEN, CYAN, (int(knob.x), int(knob.y)), knob_r)
        pygame.draw.circle(SCREEN, WHITE, (int(knob.x), int(knob.y)), knob_r, max(2,S(3)))
        draw_text("MOVE", FONT_S, DARK, (int(knob.x), int(knob.y)), True)

        if self.uses_aim_stick():
            ar = self.buttons["attack"]
            ac = pygame.Vector2(ar.center); br=min(ar.w,ar.h)//2; kr=max(S(28),int(br*0.34))
            av = self.aim_vector if self.aim_active else pygame.Vector2(0,0)
            knob = ac + av*(br-kr-S(5))
            pygame.draw.circle(SCREEN, PANEL2, (int(ac.x),int(ac.y)), br)
            pygame.draw.circle(SCREEN, WHITE, (int(ac.x),int(ac.y)), br, max(2,S(4)))
            pygame.draw.circle(SCREEN, RED, (int(knob.x),int(knob.y)), kr)
            pygame.draw.circle(SCREEN, WHITE, (int(knob.x),int(knob.y)), kr, max(2,S(3)))
            draw_text("MIRA", FONT_S, DARK, (int(knob.x),int(knob.y)), True)
        else:
            attack_label = "FACAS" if (self.player.character == HANK_KEY and self.domain_active) else "ATK"
            circle_button(self.buttons["attack"], attack_label, RED)
        circle_button(self.buttons["dash"], "DASH", CYAN)
        if self.player.character == "Sans":
            blast_color = CYAN if self.player.sans_blaster_cd <= 0 and not self.player.sans_exhausted else PANEL2
            circle_button(self.buttons["parry"], "BLAST", blast_color)
        else:
            circle_button(self.buttons["parry"], "PARRY", YELLOW)
        sans_ready = self.player.character == "Sans" and (self.domain_charge >= 100 or self.player.stamina < self.player.max_stamina*0.50) and not self.player.sans_exhausted
        dom_color = PURPLE if ((self.domain_charge >= 100 and self.player.character not in ("Glonk", "Glonk 100% Power", "Vinicius 13")) or sans_ready) else PANEL2
        dom_label = "BAD" if self.player.character == "Sans" else ("MAHO" if self.player.character == "Potential Man" else ("AUTO" if self.player.character=="Vinicius 13" else ("ART" if self.player.character==HANK_KEY else ("ULT" if self.player.character==SUKUNA_KEY else "DOM"))))
        circle_button(self.buttons["domain"], dom_label, dom_color)
        pygame.draw.rect(SCREEN, PANEL2, self.buttons["pause"], border_radius=S(16))
        draw_text("PAUSE", FONT_S, WHITE, self.buttons["pause"].center, True)
        if self.mode == "afk":
            colors = {"DUMMY": PANEL2, "INIMIGO": ORANGE, "BOSS": RED, "TIRO": PINK, "DOM": PURPLE, "UP": BLUE}
            for label, rect in self.afk_buttons.items():
                pygame.draw.rect(SCREEN, colors[label], rect, border_radius=S(12))
                draw_text(label, FONT_S, WHITE, rect.center, True)

    def draw_father_wave_fx(self, offset):
        if self.father_wave_fx_timer <= 0 or self.father_wave_fx_radius <= 0:
            return
        progress = 1.0 - self.father_wave_fx_timer / max(0.01, self.father_wave_fx_total)
        center = self.father_wave_fx_center + offset
        radius = int(self.father_wave_fx_radius * (0.70 + 0.30*progress))
        pygame.draw.circle(SCREEN, WHITE, (int(center.x), int(center.y)), radius, max(2,S(8)))
        pygame.draw.circle(SCREEN, YELLOW, (int(center.x), int(center.y)), max(1,radius-S(12)), max(1,S(3)))

    def draw_hank_aim_preview(self, offset):
        """Mira leve do Hank: 2 bordas + eixo, sem criar Surface alpha gigante por frame."""
        if self.player.character != HANK_KEY or self.domain_active or not self.aim_active:
            return
        d=pygame.Vector2(self.aim_vector)
        if d.length_squared()<=0.01: d=pygame.Vector2(self.player.facing)
        if d.length_squared()<=0.0001: d=pygame.Vector2(1,0)
        d=d.normalize()
        origin_world=pygame.Vector2(self.player.pos)+d*(self.player.radius+S(10))
        end_world=hank_range_endpoint(origin_world,d)
        origin=origin_world+offset; end=end_world+offset
        normal=pygame.Vector2(-d.y,d.x)
        half_w=max(S(20),int(self.player.radius*0.90))
        faint=(145,145,155); brighter=(195,195,205)
        pygame.draw.line(SCREEN,faint,origin+normal*half_w,end+normal*half_w,max(1,S(2)))
        pygame.draw.line(SCREEN,faint,origin-normal*half_w,end-normal*half_w,max(1,S(2)))
        # eixo tracejado: muito mais barato que um overlay 2340x1080 todo frame.
        length=max(1.0,(end-origin).length())
        pieces=max(3,min(12,int(length/max(S(55),1))))
        for i in range(0,pieces,2):
            a=origin+(end-origin)*(i/pieces); b=origin+(end-origin)*(min(pieces,i+1)/pieces)
            pygame.draw.line(SCREEN,brighter,a,b,max(1,S(2)))
        pygame.draw.circle(SCREEN,brighter,(int(end.x),int(end.y)),max(S(6),int(self.player.radius*0.32)),max(1,S(2)))

    def draw_hank_artillery(self, offset):
        if getattr(self,"hank_domain_active",False) and getattr(self,"hank_cannon_pos",None) is not None:
            p=self.hank_cannon_pos+offset; pygame.draw.circle(SCREEN,DARK,(int(p.x),int(p.y)),S(34)); pygame.draw.circle(SCREEN,RED,(int(p.x),int(p.y)),S(34),max(2,S(5))); pygame.draw.rect(SCREEN,(150,150,155),(int(p.x-S(8)),int(p.y-S(55)),S(16),S(62)),border_radius=S(5)); draw_text("CANHAO",FONT_S,RED,(p.x,p.y+S(48)),True)
        for fx in getattr(self,"hank_explosions",[]):
            ratio=clamp(1.0-fx["timer"]/max(0.01,fx["total"]),0,1); p=fx["pos"]+offset; r=int(fx["radius"]*(0.35+0.65*ratio))
            pygame.draw.circle(SCREEN,RED if fx.get("artillery") else ORANGE,(int(p.x),int(p.y)),max(1,r),max(2,S(9))); pygame.draw.circle(SCREEN,YELLOW,(int(p.x),int(p.y)),max(1,int(r*.65)),max(1,S(4)))
        for mark in getattr(self, "hank_artillery_queue", []):
            if mark.get("done", False): continue
            p = mark["pos"] + offset; img = hank_target_surface(max(S(110), int(mark["radius"]*1.55)))
            if img is not None: SCREEN.blit(img, img.get_rect(center=(int(p.x), int(p.y))))
            else:
                pygame.draw.circle(SCREEN, RED, (int(p.x), int(p.y)), int(mark["radius"]*0.72), max(2,S(4))); pygame.draw.line(SCREEN, RED, (int(p.x-S(28)), int(p.y)), (int(p.x+S(28)), int(p.y)), max(2,S(3))); pygame.draw.line(SCREEN, RED, (int(p.x), int(p.y-S(28))), (int(p.x), int(p.y+S(28))), max(2,S(3)))

    def draw_playing(self):
        if getattr(self, "mahoraga_cutscene_active", False):
            self.draw_mahoraga_cutscene()
            return
        if getattr(self, "sukuna_cutscene_active", False):
            self.draw_sukuna_cutscene()
            return
        self.draw_bg()
        offset = self.camera_offset()
        self.draw_domain_zone(offset)
        # Sukuna: zona marcada entre o primeiro e o segundo toque do ULT.
        if self.player.character == SUKUNA_KEY and getattr(self,"sukuna_ult_marked",False):
            c=self.sukuna_ult_center+offset; r=int(self.sukuna_ult_radius)
            ov=pygame.Surface((W,H),pygame.SRCALPHA)
            pygame.draw.circle(ov,(255,92,32,34),(int(c.x),int(c.y)),r)
            pygame.draw.circle(ov,(255,133,42,170),(int(c.x),int(c.y)),r,max(2,S(6)))
            pygame.draw.circle(ov,(255,205,84,115),(int(c.x),int(c.y)),max(S(18),int(r*0.18)),max(2,S(4)))
            SCREEN.blit(ov,(0,0)); draw_text("FUUGA",FONT_M,SUKUNA_FIRE,(c.x,c.y),True)
        if getattr(self,"sukuna_fuuga_fx",None):
            fx=self.sukuna_fuuga_fx; ratio=clamp(fx["timer"]/max(0.01,fx["total"]),0,1)
            a=fx["start"]+offset; b=fx["end"]+offset
            pygame.draw.line(SCREEN,SUKUNA_FIRE,a,b,max(S(12),int(S(32)*ratio)))
            pygame.draw.line(SCREEN,YELLOW,a,b,max(S(5),int(S(12)*ratio)))
            rr=int(fx["radius"]*(1.0-ratio*0.35))
            pygame.draw.circle(SCREEN,SUKUNA_FIRE,(int(b.x),int(b.y)),rr,max(2,S(10)))
            pygame.draw.circle(SCREEN,YELLOW,(int(b.x),int(b.y)),max(S(18),int(rr*.72)),max(2,S(5)))
        self.draw_father_wave_fx(offset)
        self.draw_hank_aim_preview(offset)
        self.draw_hank_artillery(offset)
        for f in self.forge_fire_trails:
            f.draw(offset)
        for plant in self.planted_pineapples:
            plant.draw(offset)
        for d in self.drops:
            d.draw(offset)
        for p in self.projectiles:
            p.draw(offset)
        for bone in self.sans_bones:
            bone.draw(offset)
        for fx in self.sans_blaster_fx:
            start=fx["start"]+offset; end=fx["end"]+offset
            ratio=clamp(fx["timer"]/max(0.01,fx["total"]),0,1)
            width=max(S(8),int(fx["width"]*(0.35+0.65*ratio)))
            # Feixe unico azul: uma unica camada reduz draw calls e travadas no Android.
            pygame.draw.line(SCREEN,CYAN,start,end,width)
        for summon in self.summons:
            summon.draw(offset)
        for a in self.orbital_anas:
            a.draw(offset)
        for serv in self.servants:
            serv.draw(offset)
        for summon in self.potential_summons:
            summon.draw(offset)
        for wall in self.vinicius_walls: wall.draw(offset)
        for turret in self.vinicius_turrets: turret.draw(offset)
        for rock in self.vinicius_rocks: rock.draw(offset)
        for e in self.enemies:
            e.draw(offset)
        for p in self.particles:
            p.draw(offset)
        self.player.draw(offset, self)
        if self.divine_burst_fx:
            fx=self.divine_burst_fx; ratio=clamp(fx["timer"]/fx["total"],0,1); c=fx["center"]+offset
            pygame.draw.circle(SCREEN,PURPLE,(int(c.x),int(c.y)),int(fx["radius"]*(1.0-0.25*ratio)),max(3,S(14)))
        for d in self.damage_texts:
            d.draw(offset)
        self.draw_hud()

        if self.game_mode=="arena_survival":
            if self.arena_inset>0:
                safe=pygame.Rect(int(self.arena_inset),int(S(175)+self.arena_inset*0.35),int(W-self.arena_inset*2),int(H-S(520)-self.arena_inset*0.70))
                pygame.draw.rect(SCREEN,ORANGE,safe,max(2,S(5)),border_radius=S(12))
            for h in self.arena_hazards:
                pp=h["pos"]+offset
                col=RED if h.get("boom") else ORANGE
                pygame.draw.circle(SCREEN,col,(int(pp.x),int(pp.y)),int(h["r"]),max(2,S(6)))
            if self.arena_reward_cards:
                self.arena_reward_rects=[]
                cw=S(360); ch=S(145); gap=S(18); total=len(self.arena_reward_cards)*cw+(len(self.arena_reward_cards)-1)*gap; xx=(W-total)/2; yy=S(195)
                for i,card in enumerate(self.arena_reward_cards):
                    r=pygame.Rect(xx+i*(cw+gap),yy,cw,ch); pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(15)); pygame.draw.rect(SCREEN,YELLOW,r,max(2,S(4)),border_radius=S(15));
                    draw_text(card[1],FONT_S,YELLOW,(r.centerx,r.y+S(34)),True); draw_wrapped_text(card[2],FONT_S,WHITE,pygame.Rect(r.x+S(12),r.y+S(60),r.w-S(24),S(70)),2,True,2); self.arena_reward_rects.append((r,card))
                draw_text("ESCOLHA RAPIDO - A ARENA NAO PAUSA",FONT_S,RED,(W/2,yy-S(26)),True)
        if self.game_mode=="infinite" and self.infinite_curses:
            draw_text(f"MALDICOES {len(self.infinite_curses)}",FONT_S,PURPLE,(W/2,S(120)),True)
        elif self.game_mode=="evolution" and self.evolution_traits:
            names=[next((x[1] for x in EVOLUTION_TRAITS if x[0]==k),k) for k in self.evolution_traits[-3:]]
            draw_text("EVOLUCOES: "+" / ".join(names),FONT_S,GREEN,(W/2,S(120)),True)
        elif self.game_mode=="rogue" and self.rogue_rule:
            nm=next((x[1] for x in ROGUE_RULES if x[0]==self.rogue_rule),self.rogue_rule); draw_text("ROGUE: "+nm,FONT_S,PURPLE,(W/2,S(120)),True)
        elif self.game_mode=="boss_rush" and self.boss_heritages:
            draw_text("HERANCAS: "+" > ".join(self.boss_heritages[-4:]),FONT_S,RED,(W/2,S(120)),True)

        # GLONK, O ULTIMO: barra gigante de boss sem trocar o inimigo por outra entidade.
        glonk_boss=next((e for e in self.enemies if isinstance(e,GlonkEnemy) and not e.dead and (e.phase=="boss" or e.death_sequence)),None)
        if glonk_boss is not None:
            bw=int(W*0.56); bh=S(28); bx=(W-bw)//2; by=S(145)
            pygame.draw.rect(SCREEN,DARK,(bx,by,bw,bh),border_radius=S(10))
            pygame.draw.rect(SCREEN,GREEN,(bx,by,bw*clamp(glonk_boss.hp/max(1,glonk_boss.max_hp),0,1),bh),border_radius=S(10))
            pygame.draw.rect(SCREEN,WHITE,(bx,by,bw,bh),width=max(2,S(3)),border_radius=S(10))
            draw_text("GLONK, O ULTIMO",FONT_M,GREEN,(W/2,by-S(26)),True)

        self.draw_controls()

        if self.glonk_event_timer > 0:
            if self.glonk_event_stage == "spawn":
                draw_text("Um Glonk apareceu.",FONT_L,GREEN,(W/2,H*0.24),True)
            elif self.glonk_event_stage == "trapped":
                draw_text("Glonk nao tem mais para onde fugir.",FONT_L,WHITE,(W/2,H*0.24),True)
            elif self.glonk_event_stage == "stopped":
                draw_text("Glonk decidiu parar de fugir.",FONT_L,GREEN,(W/2,H*0.24),True)
            elif self.glonk_event_stage == "boss":
                draw_text("GLONK",FONT_XL,GREEN,(W/2,H*0.27),True)
                draw_text("O ULTIMO",FONT_L,WHITE,(W/2,H*0.35),True)
                draw_text("Ele correu o suficiente.",FONT_M,GREEN,(W/2,H*0.42),True)

        if self.wave_banner > 0 and self.mode == "arena":
            if self.game_mode=="boss_rush": banner=f"BOSS RUSH {self.wave}/{self.boss_rush_sequence_length()}"; bcolor=RED
            elif self.game_mode=="one_vs_all": banner=f"RIVAL {self.wave}/{max(1,len(self.one_vs_all_roster))}"; bcolor=YELLOW
            elif self.game_mode=="arena_survival": banner="ARENA SEM DESCANSO"; bcolor=ORANGE
            else:
                sp=sin_encounter_for_wave(self.wave)
                if sp:
                    cfg,arch=sp; banner=("ARCEBISPO DA " if arch else "PECADO: ")+cfg["name"]; bcolor=cfg["color"]
                else:
                    banner="BOSS" if self.wave%5==0 else f"ONDA {self.wave}"; bcolor=WHITE
            draw_text(banner,FONT_XL,bcolor,(W/2,H*0.36),True)
        if self.unlock_notice_timer > 0:
            draw_text(self.unlock_notice, FONT_L, PURPLE, (W/2,H*0.20), True)
        if self.synergy_timer > 0:
            draw_text("《 SINERGIA DESPERTADA 》", FONT_M, YELLOW, (W/2,H*0.27), True)
            draw_text(self.synergy_name, FONT_L, WHITE, (W/2,H*0.33), True)
        if self.boss_domain_message_timer > 0:
            draw_text("DOMINIO DO BOSS", FONT_M, RED, (W/2, H*0.40), True)
            draw_text(self.boss_domain_message, FONT_S, WHITE, (W/2, H*0.445), True)
        if self.domain_clash_active:
            draw_text("CLASH DE DOMINIO", FONT_L, YELLOW, (W/2, H*0.475), True)
            # Centro da barra = 0 (limite para vencer). Ela cai 4 pontos/s mesmo sem sofrer dano.
            bw, bh = S(430), S(20)
            br = pygame.Rect(W/2-bw/2, H*0.525, bw, bh)
            pygame.draw.rect(SCREEN, PANEL2, br, border_radius=max(2,S(8)))
            ratio = clamp((self.domain_clash_score + 60.0) / 120.0, 0.0, 1.0)
            if ratio > 0:
                fill = pygame.Rect(br.x, br.y, int(br.w*ratio), br.h)
                pygame.draw.rect(SCREEN, YELLOW if self.domain_clash_score >= 0 else RED, fill, border_radius=max(2,S(8)))
            pygame.draw.rect(SCREEN, WHITE, br, max(1,S(2)), border_radius=max(2,S(8)))
            pygame.draw.line(SCREEN, WHITE, (br.centerx,br.y-S(3)), (br.centerx,br.bottom+S(3)), max(1,S(2)))
            draw_text(f"{self.domain_clash_timer:.1f}s   PODER {self.domain_clash_score:+.1f}", FONT_S, WHITE, (W/2, H*0.565), True)
        elif self.clash_result_timer > 0:
            draw_text(self.clash_result, FONT_M, YELLOW if "SOBERANO" in self.clash_result else RED, (W/2, H*0.49), True)
        if self.flash_screen > 0:
            surf = pygame.Surface((W,H), pygame.SRCALPHA)
            surf.fill((255,255,255,int(160*self.flash_screen/0.22)))
            SCREEN.blit(surf,(0,0))
        self.draw_domain_cutscene()

    def draw_menu(self):
        SCREEN.fill(BG)
        title = APP_TITLE
        subtitle = "Ou seja devorado...."
        title_img = FONT_TITLE.render(title, True, WHITE)
        max_w = W - SAFE*4
        if title_img.get_width() > max_w:
            ratio = max_w / title_img.get_width()
            title_img = pygame.transform.smoothscale(title_img, (int(title_img.get_width()*ratio), int(title_img.get_height()*ratio)))
        SCREEN.blit(title_img, title_img.get_rect(center=(W/2, H*0.11)))
        draw_text(subtitle, FONT_FANCY_S, GRAY, (W/2, H*0.175), True)

        # V10: menu em duas colunas para acomodar ferramentas sem esmagar a tela.
        bw = min(S(650), int(W*0.36))
        bh = S(90)
        gap_x = S(42)
        gap_y = S(24)
        left_x = W/2-gap_x/2-bw
        right_x = W/2+gap_x/2
        y0 = int(H*0.26)
        rows = [y0 + i*(bh+gap_y) for i in range(3)]
        start = pygame.Rect(left_x, rows[0], bw, bh)
        afk = pygame.Rect(left_x, rows[1], bw, bh)
        shop = pygame.Rect(left_x, rows[2], bw, bh)
        right_bh=S(62); right_gap=S(13); right_y0=rows[0]
        upgrades = pygame.Rect(right_x, right_y0, bw, right_bh)
        bestiary = pygame.Rect(right_x, right_y0+(right_bh+right_gap), bw, right_bh)
        passives = pygame.Rect(right_x, right_y0+2*(right_bh+right_gap), bw, right_bh)
        controls = pygame.Rect(right_x, right_y0+3*(right_bh+right_gap), bw, right_bh)
        for rect, color, label in [
            (start, RED, "JOGAR"), (afk, CYAN, "ZONA AFK / TESTES"), (shop, PANEL2, "LOJA PERMANENTE"),
            (upgrades, PURPLE, "TODOS OS UPGRADES"), (bestiary, ORANGE, "BESTIARIO"), (passives, PASSIVE_RARITIES["divine"]["color"], "ROLETA DE PASSIVAS"), (controls, BLUE, "EDITAR CONTROLES"),
        ]:
            pygame.draw.rect(SCREEN, color, rect, border_radius=S(22))
            draw_text(label, FONT_M if label == "JOGAR" else FONT_S, DARK if color in (CYAN, ORANGE, PASSIVE_RARITIES["divine"]["color"]) else WHITE, rect.center, True)

        # V14 FINAL: os antigos botoes ON/OFF viraram uma tela unica de CONFIGURACOES.
        settings_btn = pygame.Rect(W/2-S(320), int(H*0.68), S(640), S(62))
        pygame.draw.rect(SCREEN, BLUE, settings_btn, border_radius=S(16))
        pygame.draw.rect(SCREEN, WHITE, settings_btn, width=max(1,S(2)), border_radius=S(16))
        draw_text("CONFIGURACOES  |  AUDIO", FONT_S, WHITE, settings_btn.center, True)
        self.menu_settings_rect = settings_btn

        # Abas compactas extras. Novidades fica no canto inferior esquerdo, Conquistas logo acima.
        tab_w, tab_h = S(270), S(46)
        bottom_tab_y = H - CONTROL_SAFE_Y - tab_h - S(6)
        news = pygame.Rect(CONTROL_SAFE_X, bottom_tab_y, S(360), tab_h)
        ach = pygame.Rect(CONTROL_SAFE_X, bottom_tab_y-tab_h-S(8), tab_w, tab_h)
        missions = pygame.Rect(W-CONTROL_SAFE_X-tab_w, bottom_tab_y-tab_h-S(8), tab_w, tab_h)
        cheats = pygame.Rect(W-CONTROL_SAFE_X-tab_w, bottom_tab_y, tab_w, tab_h)
        pulse = 0.55 + 0.45 * math.sin(pygame.time.get_ticks()/240.0)
        news_edge = (255, int(220+35*pulse), int(70+80*pulse))
        pygame.draw.rect(SCREEN,CYAN,news,border_radius=S(12))
        pygame.draw.rect(SCREEN,news_edge,news,width=max(2,S(4)),border_radius=S(12))
        draw_text("NOVAS NOVIDADES!!",FONT_S,DARK,news.center,True)
        for r,label,color in [(ach,"CONQUISTAS",YELLOW),(missions,"MISSOES",PURPLE),(cheats,"CHEATS",RED)]:
            pygame.draw.rect(SCREEN,color,r,border_radius=S(12)); draw_text(label,FONT_S,DARK if color==YELLOW else WHITE,r.center,True)
        self.menu_news_rect,self.menu_achievements_rect,self.menu_missions_rect,self.menu_cheats_rect = news,ach,missions,cheats

        # V13 Forja: quatro atalhos centrais para FORJA / ITENS / ARMAS / BACKUP.
        row_y=int(H*0.745); mini_w=S(245); mini_gap=S(18)
        total4=mini_w*4+mini_gap*3; mx=W/2-total4/2
        forge=pygame.Rect(mx,row_y,mini_w,tab_h); items=pygame.Rect(mx+mini_w+mini_gap,row_y,mini_w,tab_h)
        weapons=pygame.Rect(mx+(mini_w+mini_gap)*2,row_y,mini_w,tab_h); backup=pygame.Rect(mx+(mini_w+mini_gap)*3,row_y,mini_w,tab_h)
        for r,label,color in [(forge,"FORJA",ORANGE),(items,"ITENS",CYAN),(weapons,"ARMAS",PURPLE),(backup,"BACKUP",GREEN)]:
            pygame.draw.rect(SCREEN,color,r,border_radius=S(12)); draw_text(label,FONT_S,DARK if color in (ORANGE,CYAN,GREEN) else WHITE,r.center,True)
        self.menu_forge_rect,self.menu_items_rect,self.menu_weapons_rect,self.menu_backup_rect=forge,items,weapons,backup

        victories = set(SAVE.get("father_victories", []))
        progress = len([x for x in FATHER_UNLOCK_CHARACTERS if x in victories])
        draw_text(f"MOEDAS {SAVE['coins']}   |   MELHOR ONDA {SAVE['best_wave']}   |   KOs {SAVE['best_kills']}", FONT_S, GRAY, (W/2, H*0.80), True)
        sentinel_victories = set(SAVE.get("sentinel_victories", []))
        sentinel_progress = len([x for x in FATHER_UNLOCK_CHARACTERS if x in sentinel_victories])
        if SAVE.get("hank_unlocked", False):
            draw_text("HANK J. WIMBLETON DESBLOQUEADO", FONT_S, RED, (W/2, H*0.85), True)
        elif SAVE.get("father_unlocked", False):
            draw_text(f"COLOSSO DO CAOS DESBLOQUEADO   |   PROGRESSO HANK: {sentinel_progress}/{len(FATHER_UNLOCK_CHARACTERS)}", FONT_S, WHITE, (W/2, H*0.85), True)
        elif SAVE.get("kayk_unlocked", False):
            draw_text(f"KAYK DESBLOQUEADO   |   PROGRESSO COLOSSO DO CAOS: {progress}/{len(FATHER_UNLOCK_CHARACTERS)}", FONT_S, PURPLE, (W/2, H*0.85), True)
        else:
            draw_text("Derrote o Colosso do Caos para desbloquear Kayk", FONT_S, PURPLE, (W/2, H*0.85), True)
        draw_text("JOYSTICK | ATK | DASH | PARRY | DOM | PAUSE", FONT_S, GRAY, (W/2, H-CONTROL_SAFE_Y-S(4)), True)

        self.menu_start_rect = start
        self.menu_afk_rect = afk
        self.menu_shop_rect = shop
        self.menu_upgrades_rect = upgrades
        self.menu_bestiary_rect = bestiary
        self.menu_passives_rect = passives
        self.menu_controls_rect = controls

    def draw_character_select(self):
        SCREEN.fill(BG)
        mode_text = ("PARTIDA - "+GAME_MODES.get(self.game_mode,GAME_MODES["normal"])["name"]) if self.selection_target == "arena" else "ZONA AFK"
        draw_text("PERSONAGENS", FONT_L, WHITE, (W/2, S(50)), True)
        draw_text(mode_text + "  |  DESLIZE PARA TROCAR", FONT_S, CYAN, (W/2, S(92)), True)

        tab_w, tab_h = S(420), S(58)
        tab_gap = S(18)
        tx = W/2 - tab_w - tab_gap/2
        tabs_y = S(118)
        main_tab = pygame.Rect(tx, tabs_y, tab_w, tab_h)
        beta_tab = pygame.Rect(W/2 + tab_gap/2, tabs_y, tab_w, tab_h)
        for r, label, active in [(main_tab, "PERSONAGENS", self.character_tab == "characters"),
                                 (beta_tab, "PERSONAGENS EM BETA", self.character_tab == "beta")]:
            pygame.draw.rect(SCREEN, CYAN if active else PANEL2, r, border_radius=S(15))
            pygame.draw.rect(SCREEN, WHITE if active else GRAY, r, width=max(1,S(2)), border_radius=S(15))
            draw_text(label, FONT_S, DARK if active else WHITE, r.center, True)
        self.character_main_tab_rect = main_tab
        self.character_beta_tab_rect = beta_tab

        back = pygame.Rect(CONTROL_SAFE_X, H-CONTROL_SAFE_Y-S(52), S(210), S(52))
        pygame.draw.rect(SCREEN, PANEL2, back, border_radius=S(14))
        draw_text("VOLTAR", FONT_S, WHITE, back.center, True)
        self.character_back_rect = back
        self.character_rects = []
        self.character_stat_plus_rects = []
        self.character_play_rect = pygame.Rect(0,0,0,0)
        self.character_passive_rect = pygame.Rect(0,0,0,0)
        self.character_prev_rect = pygame.Rect(0,0,0,0)
        self.character_next_rect = pygame.Rect(0,0,0,0)

        order = self.current_character_order()
        if not order:
            panel = pygame.Rect(W*0.16, H*0.27, W*0.68, H*0.48)
            pygame.draw.rect(SCREEN, PANEL, panel, border_radius=S(26))
            draw_text("VAZIO POR ENQUANTO", FONT_M, WHITE, panel.center, True)
            return

        # Carrossel a esquerda e ficha detalhada a direita.
        self.character_carousel_index %= len(order)
        selected = self.selected_carousel_character()
        drag_offset = 0
        if self.character_swipe_start is not None and self.character_swipe_current is not None:
            drag_offset = int(clamp(self.character_swipe_current.x-self.character_swipe_start.x, -W*0.12, W*0.12))

        area = pygame.Rect(CONTROL_SAFE_X, S(205), int(W*0.49), H-S(310))
        centers = [area.x+area.w*0.18, area.x+area.w*0.50, area.x+area.w*0.82]
        idxs = [(self.character_carousel_index-1)%len(order), self.character_carousel_index, (self.character_carousel_index+1)%len(order)]
        for slot, idx in enumerate(idxs):
            if len(order) == 1 and slot != 1:
                continue
            name = order[idx]
            cfg = CHARACTER_CONFIG[name]
            center_slot = slot == 1
            cw = int(area.w*(0.40 if center_slot else 0.27))
            ch = int(area.h*(0.78 if center_slot else 0.61))
            cx = centers[slot] + drag_offset
            cy = area.centery
            r = pygame.Rect(int(cx-cw/2), int(cy-ch/2), cw, ch)
            unlocked = self.character_unlocked(name)
            color = cfg["color"] if unlocked else GRAY
            pygame.draw.rect(SCREEN, PANEL2 if center_slot else PANEL, r, border_radius=S(22))
            pygame.draw.rect(SCREEN, color, r, width=max(2,S(5 if center_slot else 3)), border_radius=S(22))
            # Catalogo mostra apenas o NOME. Titulos aparecem depois, na ficha/HUD.
            card_name = "LIRA SOLIS" if name == LIRA_KEY else ("HANK" if name == HANK_KEY else ("SUKUNA" if name == SUKUNA_KEY else name.upper()))
            long_name = False
            draw_text(card_name, FONT_S if long_name else (FONT_M if center_slot else FONT_S), color, (r.centerx, r.y+S(38)), True)
            if center_slot:
                draw_text("BETA" if is_beta_character(name) else f"LV {evolution_level(name)}", FONT_M, CYAN if is_beta_character(name) else YELLOW, (r.centerx, r.y+S(88)), True)
                draw_text(cfg["weapon_name"], FONT_S, WHITE if unlocked else GRAY, (r.centerx, r.y+S(137)), True)
                draw_wrapped_text(cfg["desc"], FONT_S, GRAY, pygame.Rect(r.x+S(16),r.y+S(175),r.w-S(32),S(90)),3,True,3)
                draw_text(cfg["domain"], FONT_S, PURPLE if unlocked else GRAY, (r.centerx, r.bottom-S(78)), True)
                draw_text("DESBLOQUEADO" if unlocked else "BLOQUEADO", FONT_S, GREEN if unlocked else RED, (r.centerx, r.bottom-S(35)), True)
            else:
                draw_text("BETA" if is_beta_character(name) else f"LV {evolution_level(name)}", FONT_S, CYAN if is_beta_character(name) else YELLOW, (r.centerx, r.centery), True)
                draw_text("TOQUE", FONT_S, GRAY, (r.centerx, r.bottom-S(35)), True)
            self.character_rects.append((r, name, unlocked, idx))

        # Setas tambem funcionam para quem prefere tocar em vez de deslizar.
        prev = pygame.Rect(area.x, area.bottom+S(12), S(170), S(48))
        nxt = pygame.Rect(area.right-S(170), area.bottom+S(12), S(170), S(48))
        for r,label in [(prev,"< ANTERIOR"),(nxt,"PROXIMO >")]:
            pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(13)); draw_text(label,FONT_S,WHITE,r.center,True)
        self.character_prev_rect, self.character_next_rect = prev, nxt

        # Ficha de status.
        cfg = CHARACTER_CONFIG[selected]
        beta_selected = is_beta_character(selected)
        prof = evolution_profile(selected)
        passive_preview = passive_static_effects(passive_equipped_keys(selected)) if not beta_selected else passive_static_effects([])
        detail = pygame.Rect(int(W*0.52), S(205), int(W*0.45)-CONTROL_SAFE_X, H-S(290))
        pygame.draw.rect(SCREEN, PANEL, detail, border_radius=S(22))
        pygame.draw.rect(SCREEN, cfg["color"], detail, width=max(2,S(4)), border_radius=S(22))
        selected_title = ("VASCO, O APOSTADOR INCANSAVEL" if selected == "Vasco" else
                          ("LIRA SOLIS, A C#NSUR#" if selected == LIRA_KEY else
                           ("HANK J. WIMBLETON" if selected == HANK_KEY else ("RIP_INDRA" if selected==RIP_INDRA_KEY else selected.upper()))))
        draw_text(f"{selected_title}  |  " + ("BETA" if beta_selected else f"NIVEL {evolution_level(selected)}"), FONT_M if selected != "Vasco" else FONT_S, cfg["color"], (detail.x+S(22),detail.y+S(22)))
        if beta_selected:
            draw_text("PROGRESSAO DESATIVADA", FONT_S, CYAN, (detail.x+S(22),detail.y+S(70)))
            draw_text("Beta nao ganha pontos, moedas, recordes, missoes ou conquistas.", FONT_S, GRAY, (detail.x+S(22),detail.y+S(103)))
        else:
            draw_text(f"PONTOS DISPONIVEIS: {prof.get('points',0)}", FONT_S, YELLOW, (detail.x+S(22),detail.y+S(70)))
            draw_text("Ponto por onda: 100% GARANTIDO (+1 por onda vencida)", FONT_S, GREEN, (detail.x+S(22),detail.y+S(103)))

        # Valores reais com upgrades permanentes + evolucao aplicados, para a ficha ser precisa.
        actual_damage = cfg["damage"] * (1 + 0.08 * SAVE.get("damage_level",0)) * (1 + 0.03 * prof.get("strength",0)) * max(.10,1.0+passive_preview.get("damage",0.0))
        actual_speed = cfg["speed"] * (1 + 0.03 * SAVE.get("speed_level",0)) * (1 + 0.015 * prof.get("speed",0)) * max(.10,1.0+passive_preview.get("move",0.0))
        actual_hp = 1 if selected in ("Sans", "Glonk 100% Power") else (cfg["hp"] + SAVE.get("vitality_level",0)*8 + prof.get("hp",0)*6) * max(.10,1.0+passive_preview.get("hp",0.0))
        hp_to_sta = prof.get("hp",0)*3 if selected == "Sans" else (prof.get("hp",0)*2 if selected == "Glonk 100% Power" else 0)
        actual_sta = cfg["stamina"] + SAVE.get("vitality_level",0)*6 + SAVE.get("stamina_level",0)*10 + prof.get("stamina",0)*5 + hp_to_sta
        actual_regen = cfg["regen"] * (1 + 0.06 * SAVE.get("regen_level",0)) * (1 + 0.015 * prof.get("stamina",0))
        parry_window = 0.16 + 0.006 * prof.get("parry",0)
        resist_pct = 100*(1-(max(0.55,1-0.03*SAVE.get("armor_level",0))*max(0.625,1-0.015*prof.get("resistance",0))))
        draw_text(f"ATUAL: HP {int(actual_hp)} | STA {int(actual_sta)} | DANO {actual_damage:.1f} | VEL {actual_speed:.0f}", FONT_S, WHITE, (detail.x+S(22),detail.y+S(133)))
        if selected == "Sans":
            draw_text(f"REGEN {actual_regen:.1f}/s | BLASTER 15s | SEM PARRY", FONT_S, GRAY, (detail.x+S(22),detail.y+S(163)))
        else:
            draw_text(f"REGEN {actual_regen:.1f}/s | PARRY {parry_window:.3f}s | REDUCAO {resist_pct:.0f}%", FONT_S, GRAY, (detail.x+S(22),detail.y+S(163)))

        eq_keys=passive_equipped_keys(selected) if not beta_selected else []
        eq_labels=[PASSIVE_BY_KEY[k]["name"] for k in eq_keys]
        draw_text("PASSIVAS: "+(" | ".join(eq_labels) if eq_labels else "NENHUMA"),FONT_S,DIVINE_BLUE,(detail.x+S(22),detail.y+S(188)))
        row_y = detail.y + S(220)
        row_h = max(S(56), int((detail.h-S(315))/6))
        for stat in EVOLUTION_STAT_KEYS:
            alloc = int(prof.get(stat,0))
            rating = CHARACTER_BASE_RATINGS[selected][stat] + alloc
            y = row_y
            label = "BLASTER" if selected=="Sans" and stat=="parry" else EVOLUTION_STAT_LABELS[stat]
            suffix = "" if beta_selected else f"  (+{alloc})"
            draw_text(f"{label}: {rating}{suffix}", FONT_S, WHITE, (detail.x+S(22), y+S(6)))
            if selected=="Sans" and stat=="parry":
                desc = "Sem Parry: botao dedicado dispara o Blaster"
            elif selected=="Sans" and stat=="hp":
                desc = "HP fixo em 1"
            elif selected=="Sans" and stat=="resistance":
                desc = "Esquiva automatica consome Estamina"
            elif selected=="Glonk 100% Power" and stat=="hp":
                desc = "HP fixo em 1; cada ponto vira +2 STA"
            else:
                desc = EVOLUTION_STAT_DESCS[stat]
            draw_text(desc, FONT_S, GRAY, (detail.x+S(250), y+S(6)))
            if beta_selected:
                lock = pygame.Rect(detail.right-S(82), y, S(66), S(42))
                pygame.draw.rect(SCREEN, PANEL2, lock, border_radius=S(10))
                draw_text("BETA", FONT_S, GRAY, lock.center, True)
            else:
                plus = pygame.Rect(detail.right-S(62), y, S(46), S(42))
                can = prof.get("points",0)>0 and alloc<MAX_EVOLUTION_STAT
                pygame.draw.rect(SCREEN, GREEN if can else PANEL2, plus, border_radius=S(10))
                draw_text("+" if alloc<MAX_EVOLUTION_STAT else "MAX", FONT_S, DARK if can else GRAY, plus.center, True)
                self.character_stat_plus_rects.append((plus, stat, can))
                # Barra de progresso do investimento, 25 = max.
                bx = detail.x+S(22); by = y+S(43); bw = detail.w-S(105); bh=S(8)
                pygame.draw.rect(SCREEN, DARK, (bx,by,bw,bh), border_radius=S(4))
                if alloc>0:
                    pygame.draw.rect(SCREEN, cfg["color"], (bx,by,bw*(alloc/MAX_EVOLUTION_STAT),bh), border_radius=S(4))
            row_y += row_h

        unlocked = self.character_unlocked(selected)
        passive_btn=pygame.Rect(detail.right-S(300), detail.y+S(58), S(270), S(42))
        passive_available=(not beta_selected and unlocked)
        pygame.draw.rect(SCREEN, PASSIVE_RARITIES["divine"]["color"] if passive_available else PANEL2, passive_btn, border_radius=S(12))
        draw_text("ROLETA PASSIVAS" if passive_available else "PASSIVAS BLOQUEADAS",FONT_S,DARK if passive_available else GRAY,passive_btn.center,True)
        self.character_passive_rect=passive_btn
        play = pygame.Rect(detail.x, H-CONTROL_SAFE_Y-S(58), detail.w, S(58))
        pygame.draw.rect(SCREEN, cfg["color"] if unlocked else PANEL2, play, border_radius=S(15))
        launch = "ENTRAR NA ZONA AFK" if self.selection_target == "afk" else "JOGAR COM ESTE PERSONAGEM"
        draw_text(launch if unlocked else "PERSONAGEM BLOQUEADO", FONT_S, DARK if unlocked else GRAY, play.center, True)
        self.character_play_rect = play

    def all_upgrade_entries(self):
        out = [("UNIVERSAL", card) for card in UNIVERSAL_UPGRADES]
        out += [("HIBRIDO", card) for card in HYBRID_UPGRADES]
        for char, cards in CHARACTER_UPGRADES.items():
            for card in cards:
                out.append((char.upper(), card))
        return out

    def upgrade_catalog_entries(self):
        tab=getattr(self,"upgrade_catalog_tab","found")
        entries=self.all_upgrade_entries()
        if tab=="found":
            discovered=set(SAVE.get("upgrade_discovered",[]))
            return [(source,card) for source,card in entries if card[3] in discovered]
        if tab=="signatures":
            return [(source,card) for source,card in entries if source not in ("UNIVERSAL","HIBRIDO")]
        return entries

    def _passive_card(self, item, rect, discovered=True, equipped=False):
        rarity=PASSIVE_RARITIES[item["rarity"]]; border=rarity["border"]; color=(border if item["rarity"]=="demonic" else rarity["color"])
        fill=(30,31,38) if item["rarity"]!="demonic" else rarity["color"]
        pygame.draw.rect(SCREEN,fill,rect,border_radius=S(16))
        pygame.draw.rect(SCREEN,border,rect,max(2,S(4 if equipped else 2)),border_radius=S(16))
        title=item["name"] if discovered else "???"
        draw_text(title.upper(),FONT_S,color,(rect.x+S(16),rect.y+S(15)))
        draw_text(rarity["name"],FONT_S,border,(rect.x+S(16),rect.y+S(76)))
        if discovered:
            draw_text(item["en"],FONT_S,GRAY,(rect.x+S(16),rect.y+S(48)))
            draw_wrapped_text(item["desc"],FONT_S,WHITE,pygame.Rect(rect.x+S(16),rect.y+S(105),rect.w-S(32),rect.h-S(126)),3,False,3)
        else:
            draw_text("AINDA NAO DESCOBERTA",FONT_S,GRAY,rect.center,True)

    def draw_passive_catalog(self):
        SCREEN.fill(BG)
        draw_text("PASSIVAS DA ROLETA",FONT_L,WHITE,(W/2,S(52)),True)
        draw_text("VISTAS / EQUIPADAS OU TODAS DO JOGO",FONT_S,GRAY,(W/2,S(98)),True)
        tabw=S(360); gap=S(16); x=W/2-tabw-gap/2
        known=pygame.Rect(x,S(122),tabw,S(50)); allr=pygame.Rect(W/2+gap/2,S(122),tabw,S(50))
        for r,label,key in ((known,"VISTAS / EQUIPADAS","known"),(allr,"TODAS DO JOGO","all")):
            active=self.passive_catalog_tab==key
            pygame.draw.rect(SCREEN,CYAN if active else PANEL2,r,border_radius=S(12)); draw_text(label,FONT_S,DARK if active else WHITE,r.center,True)
        self.passive_catalog_known_rect=known; self.passive_catalog_all_rect=allr
        discovered=set(SAVE.get("passive_discovered",[]))
        equipped_global=set()
        root=SAVE.get("character_passives",{})
        if isinstance(root,dict):
            for prof in root.values():
                if isinstance(prof,dict): equipped_global.update(k for k in prof.get("equipped",[]) if k in PASSIVE_BY_KEY)
        if self.passive_catalog_tab=="known":
            entries=[x for x in PASSIVES if x["key"] in discovered or x["key"] in equipped_global]
        else: entries=list(PASSIVES)
        per=6; pages=max(1,math.ceil(max(1,len(entries))/per)); self.passive_catalog_page=int(clamp(self.passive_catalog_page,0,pages-1))
        subset=entries[self.passive_catalog_page*per:(self.passive_catalog_page+1)*per]
        cols=3; gapx=S(18); gapy=S(16); left=CONTROL_SAFE_X; top=S(195); cw=int((W-left*2-gapx*2)/3); ch=S(315)
        for i,item in enumerate(subset):
            r=pygame.Rect(left+(i%cols)*(cw+gapx),top+(i//cols)*(ch+gapy),cw,ch)
            self._passive_card(item,r,True,item["key"] in equipped_global)
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(50),S(210),S(48)); prev=pygame.Rect(W/2-S(280),H-CONTROL_SAFE_Y-S(50),S(120),S(48)); nxt=pygame.Rect(W/2+S(160),H-CONTROL_SAFE_Y-S(50),S(120),S(48)); roll=pygame.Rect(W-CONTROL_SAFE_X-S(300),H-CONTROL_SAFE_Y-S(50),S(300),S(48))
        for r,l in ((back,"VOLTAR"),(prev,"<"),(nxt,">")):
            pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(12)); draw_text(l,FONT_S,WHITE,r.center,True)
        pygame.draw.rect(SCREEN,DIVINE_BLUE,roll,border_radius=S(12)); draw_text("VOLTAR A ROLETA",FONT_S,DARK,roll.center,True)
        draw_text(f"PAGINA {self.passive_catalog_page+1}/{pages}",FONT_S,GRAY,(W/2,H-CONTROL_SAFE_Y-S(26)),True)
        self.passive_catalog_back_rect=back; self.passive_catalog_prev_rect=prev; self.passive_catalog_next_rect=nxt; self.passive_catalog_roll_rect=roll

    def passive_roll_characters(self):
        return [c for c in CHARACTER_ORDER if not is_beta_character(c) and self.character_unlocked(c)]

    def open_passive_roll(self, character, return_state="character_select"):
        chars=self.passive_roll_characters()
        if not chars:return
        if character not in chars: character=chars[0]
        self.passive_roll_character=character; self.passive_roll_return_state=return_state
        self.passive_roll_slot=0; self.passive_roll_result=None; self.passive_roll_display_key=None; self.passive_roll_message=""
        self.passive_roll_spinning=False; self.passive_roll_sequence=[]; self.passive_auto_mode=False; self.passive_auto_warning=False
        self.passive_roll_scroll_pos=0.0; self.passive_roll_elapsed=0.0; self.passive_roll_last_center_index=0
        passive_character_profile(character); save_data(SAVE); self.state="passive_roll"

    def cycle_passive_roll_character(self, step):
        if self.passive_roll_spinning:return
        chars=self.passive_roll_characters()
        if not chars:return
        try:i=chars.index(self.passive_roll_character)
        except ValueError:i=0
        self.passive_roll_character=chars[(i+step)%len(chars)]
        self.passive_roll_result=None; self.passive_roll_display_key=None; self.passive_roll_message=""; self.passive_auto_mode=False
        passive_character_profile(self.passive_roll_character); save_data(SAVE)

    def _build_passive_spin_sequence(self, final_key):
        # O resultado real ja foi sorteado; esta fila e apenas animacao.
        count=random.randint(38,52)
        seq=[passive_roll_key(self.passive_roll_character) for _ in range(max(1,count-1))]
        final_item=PASSIVE_BY_KEY.get(final_key,{})
        # Near miss visual: uma raridade absurda pode cruzar o centro logo antes da vencedora.
        if final_item.get("rarity") not in ("mythic","secret","divine","demonic") and random.random()<0.68:
            high_pool=[x["key"] for x in PASSIVES if x.get("rollable",True) and x["rarity"] in ("mythic","secret","divine","demonic")]
            if high_pool and len(seq)>=4:
                seq[-2]=random.choice(high_pool)
                if random.random()<0.35:
                    seq[-3]=random.choice(high_pool)
        seq.append(final_key)
        return seq

    def start_passive_spin(self, from_auto=False, ignore_protection=False):
        if self.passive_roll_spinning:return False
        char=self.passive_roll_character; prof=evolution_profile(char)
        pp=passive_character_profile(char); current=pp["equipped"][self.passive_roll_slot]
        if from_auto and not ignore_protection and current and passive_auto_stop_hit(current):
            self.passive_auto_warning=True; self.passive_auto_mode=False
            return False
        if prof.get("points",0)<=0:
            self.passive_auto_mode=False; self.passive_roll_message="SEM PONTOS DE EVOLUCAO"; AUDIO.play("hurt",.5,120); return False
        final_key=passive_roll_key(char)
        prof["points"]-=1
        self.passive_roll_final_key=final_key
        self.passive_roll_sequence=self._build_passive_spin_sequence(final_key)
        self.passive_roll_sequence_index=0
        self.passive_roll_display_key=self.passive_roll_sequence[0]
        self.passive_roll_result=None
        self.passive_roll_spinning=True
        self.passive_roll_scroll_pos=0.0
        self.passive_roll_elapsed=0.0
        self.passive_roll_duration=random.uniform(5.2,6.6)
        self.passive_roll_last_center_index=0
        self.passive_roll_message="ROLANDO..."
        save_data(SAVE)
        AUDIO.play("click",.45,60)
        return True

    def roll_passive(self):
        self.passive_auto_mode=False
        return self.start_passive_spin(False)

    def finish_passive_spin(self):
        key=self.passive_roll_final_key
        if key not in PASSIVE_BY_KEY:
            self.passive_roll_spinning=False; return
        ok,cleared=passive_set_slot(self.passive_roll_character,key,self.passive_roll_slot)
        self.passive_roll_result=key; self.passive_roll_display_key=key; self.passive_roll_spinning=False; self.passive_roll_anim=1.0
        item=PASSIVE_BY_KEY[key]; rarity=PASSIVE_RARITIES[item["rarity"]]["name"]
        self.passive_roll_message=f"{rarity} | SLOT {self.passive_roll_slot+1}: {item['name']}"
        if cleared:
            self.passive_roll_message += " | OUTRO SLOT ESVAZIADO POR CONFLITO"
        save_data(SAVE); AUDIO.play("unlock",1.0)
        if self.passive_auto_mode:
            if passive_auto_stop_hit(key):
                self.passive_auto_mode=False
                self.passive_roll_message=f"AUTO PAROU: {item['name']}"
            elif evolution_profile(self.passive_roll_character).get("points",0)<=0:
                self.passive_auto_mode=False
                self.passive_roll_message="AUTO ENCERRADO: SEM PONTOS"
            else:
                self.passive_auto_delay=0.45

    def update_passive_roll_system(self, dt):
        if self.state!="passive_roll":return
        if self.passive_roll_spinning:
            self.passive_roll_elapsed += dt
            t=clamp(self.passive_roll_elapsed/max(0.01,self.passive_roll_duration),0.0,1.0)
            eased=1.0-(1.0-t)**4
            target=max(0,len(self.passive_roll_sequence)-1)
            self.passive_roll_scroll_pos=target*eased
            center_idx=int(clamp(round(self.passive_roll_scroll_pos),0,target))
            self.passive_roll_sequence_index=center_idx
            self.passive_roll_display_key=self.passive_roll_sequence[center_idx]
            if center_idx!=self.passive_roll_last_center_index:
                self.passive_roll_last_center_index=center_idx
                AUDIO.play("click",.16,28)
            if t>=1.0:
                self.passive_roll_scroll_pos=float(target)
                self.finish_passive_spin(); return
        elif self.passive_auto_mode:
            self.passive_auto_delay=max(0.0,self.passive_auto_delay-dt)
            if self.passive_auto_delay<=0:
                self.start_passive_spin(True, ignore_protection=True)

    def start_passive_auto(self, ignore_protection=False):
        if self.passive_roll_spinning:
            self.passive_auto_mode=False
            self.passive_roll_message="AUTO DESLIGADO APOS ESTE GIRO"
            return
        if self.passive_auto_mode:
            self.passive_auto_mode=False; self.passive_roll_message="ROLETA AUTOMATICA PARADA"; return
        pp=passive_character_profile(self.passive_roll_character)
        current=pp["equipped"][self.passive_roll_slot]
        if current and passive_auto_stop_hit(current) and not ignore_protection:
            self.passive_auto_warning=True
            return
        self.passive_auto_warning=False
        self.passive_auto_mode=True; self.passive_auto_delay=0.05
        self.passive_roll_message="ROLETA AUTOMATICA ATIVA"

    def open_passive_auto_config(self):
        self.passive_auto_mode=False; self.passive_auto_config_page=0; self.state="passive_auto_config"

    def draw_passive_auto_config(self):
        SCREEN.fill(BG)
        draw_text("FILTROS DA ROLETA AUTOMATICA",FONT_L,WHITE,(W/2,S(48)),True)
        draw_text("O AUTO PARA SE VIER QUALQUER RARIDADE OU PASSIVA MARCADA",FONT_S,GRAY,(W/2,S(92)),True)
        rar=set(SAVE.get("passive_auto_stop_rarities",[])); keys=set(SAVE.get("passive_auto_stop_keys",[]))
        self.passive_auto_rarity_rects=[]
        rw=S(235); rh=S(48); gap=S(10); total=rw*5+gap*4; x0=W/2-total/2
        for i,rkey in enumerate(PASSIVE_ROLL_ORDER):
            info=PASSIVE_RARITIES[rkey]; row=i//5; col=i%5; r=pygame.Rect(x0+col*(rw+gap),S(125)+row*S(58),rw,rh)
            active=rkey in rar; fill=info["border"] if active else PANEL2
            pygame.draw.rect(SCREEN,fill,r,border_radius=S(11)); pygame.draw.rect(SCREEN,info["border"],r,max(1,S(2)),border_radius=S(11))
            draw_text(("✓ " if active else "")+info["name"],FONT_S,DARK if active and rkey!="demonic" else WHITE,r.center,True)
            self.passive_auto_rarity_rects.append((r,rkey))
        entries=[x for x in PASSIVES if x.get("rollable",True)]
        per=8; pages=max(1,math.ceil(len(entries)/per)); self.passive_auto_config_page=int(clamp(self.passive_auto_config_page,0,pages-1))
        subset=entries[self.passive_auto_config_page*per:(self.passive_auto_config_page+1)*per]
        self.passive_auto_key_rects=[]; cols=4; gapx=S(12); left=CONTROL_SAFE_X; top=S(270); cw=int((W-left*2-gapx*3)/4); ch=S(135)
        for i,item in enumerate(subset):
            r=pygame.Rect(left+(i%cols)*(cw+gapx),top+(i//cols)*(ch+S(12)),cw,ch); active=item["key"] in keys; info=PASSIVE_RARITIES[item["rarity"]]
            pygame.draw.rect(SCREEN,(45,47,58) if not active else (70,72,82),r,border_radius=S(13)); pygame.draw.rect(SCREEN,info["border"],r,max(2,S(5 if active else 2)),border_radius=S(13))
            draw_text(("✓ " if active else "")+item["name"].upper(),FONT_S,info["border"],(r.centerx,r.y+S(34)),True)
            draw_text(info["name"],FONT_S,GRAY,(r.centerx,r.y+S(78)),True); self.passive_auto_key_rects.append((r,item["key"]))
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(50),S(210),S(48)); prev=pygame.Rect(W/2-S(250),H-CONTROL_SAFE_Y-S(50),S(130),S(48)); nxt=pygame.Rect(W/2+S(120),H-CONTROL_SAFE_Y-S(50),S(130),S(48))
        clear=pygame.Rect(W-CONTROL_SAFE_X-S(250),H-CONTROL_SAFE_Y-S(50),S(250),S(48))
        for r,l in ((back,"VOLTAR"),(prev,"<"),(nxt,">"),(clear,"LIMPAR TUDO")):
            pygame.draw.rect(SCREEN,PANEL2 if l!="LIMPAR TUDO" else RED,r,border_radius=S(12)); draw_text(l,FONT_S,WHITE,r.center,True)
        draw_text(f"PAGINA {self.passive_auto_config_page+1}/{pages}",FONT_S,GRAY,(W/2,H-CONTROL_SAFE_Y-S(24)),True)
        self.passive_auto_config_back_rect=back; self.passive_auto_config_prev_rect=prev; self.passive_auto_config_next_rect=nxt; self.passive_auto_config_clear_rect=clear

    def draw_passive_roll(self):
        SCREEN.fill(BG); char=self.passive_roll_character; prof=evolution_profile(char); pp=passive_character_profile(char)
        draw_text("ROLETA DE PASSIVAS",FONT_L,WHITE,(W/2,S(45)),True)
        cprev=pygame.Rect(W/2-S(690),S(76),S(90),S(44)); cnext=pygame.Rect(W/2+S(600),S(76),S(90),S(44))
        for r,l in ((cprev,"<"),(cnext,">")):pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(10));draw_text(l,FONT_M,WHITE,r.center,True)
        self.passive_roll_char_prev_rect=cprev; self.passive_roll_char_next_rect=cnext
        draw_text(f"{char.upper()}  |  {prof.get('points',0)} PONTOS DE EVOLUCAO",FONT_M,CYAN,(W/2,S(96)),True)
        draw_text("GIROU NO SLOT = A PASSIVA ANTIGA SOME",FONT_S,RED,(W/2,S(130)),True)
        self.passive_roll_slot_rects=[]
        for i in range(2):
            r=pygame.Rect(CONTROL_SAFE_X,S(170)+i*S(170),S(720),S(145)); active=i==self.passive_roll_slot; k=pp["equipped"][i]
            pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(18)); pygame.draw.rect(SCREEN,YELLOW if active else GRAY,r,max(2,S(5 if active else 2)),border_radius=S(18))
            if k:
                item=PASSIVE_BY_KEY[k]; col=PASSIVE_RARITIES[item["rarity"]]["border"]
                draw_text(f"SLOT {i+1} | {item['name'].upper()}",FONT_M,col,(r.x+S(20),r.y+S(18)))
                draw_wrapped_text(item["desc"],FONT_S,WHITE,pygame.Rect(r.x+S(20),r.y+S(70),r.w-S(40),S(58)),2,False,2)
            else: draw_text(f"SLOT {i+1} | VAZIO",FONT_M,GRAY,(r.x+S(20),r.centery-S(20)))
            self.passive_roll_slot_rects.append(r)
        rr=pygame.Rect(W-S(1050),S(160),S(950),S(455)); pygame.draw.rect(SCREEN,(24,25,33),rr,border_radius=S(24)); pygame.draw.rect(SCREEN,DIVINE_BLUE,rr,max(1,S(2)),border_radius=S(24))
        center_y=rr.centery; spacing=S(92); card_h=S(76)
        center_box=pygame.Rect(rr.x+S(24),center_y-card_h//2,rr.w-S(48),card_h); pygame.draw.rect(SCREEN,WHITE,center_box,max(2,S(3)),border_radius=S(14))
        old_clip=SCREEN.get_clip(); SCREEN.set_clip(rr.inflate(-S(8),-S(8)))
        if self.passive_roll_spinning and self.passive_roll_sequence:
            pos=self.passive_roll_scroll_pos; base=int(math.floor(pos))
            for idx in range(max(0,base-4),min(len(self.passive_roll_sequence),base+6)):
                key=self.passive_roll_sequence[idx]; item=PASSIVE_BY_KEY.get(key)
                if not item: continue
                cy=center_y+(pos-idx)*spacing
                if cy<rr.top-S(70) or cy>rr.bottom+S(70): continue
                info=PASSIVE_RARITIES[item["rarity"]]; near=clamp(1.0-abs(cy-center_y)/max(1,spacing*2.2),0.0,1.0)
                cw=int((rr.w-S(75))*(0.88+0.12*near)); cr=pygame.Rect(rr.centerx-cw//2,int(cy-card_h/2),cw,card_h)
                fill=(21,21,25) if item["rarity"]=="demonic" else (42,43,52)
                pygame.draw.rect(SCREEN,fill,cr,border_radius=S(13)); pygame.draw.rect(SCREEN,info["border"],cr,max(2,S(2+3*near)),border_radius=S(13))
                draw_text(item["name"].upper(),FONT_M if near>.65 else FONT_S,info["border"],(cr.centerx,cr.centery-S(10)),True)
                draw_text(info["name"],FONT_S,GRAY,(cr.centerx,cr.centery+S(22)),True)
        else:
            display=self.passive_roll_result or self.passive_roll_display_key
            if display and display in PASSIVE_BY_KEY:
                item=PASSIVE_BY_KEY[display]; info=PASSIVE_RARITIES[item["rarity"]]
                cr=pygame.Rect(rr.x+S(35),center_y-S(88),rr.w-S(70),S(176)); fill=(21,21,25) if item["rarity"]=="demonic" else PANEL2
                pygame.draw.rect(SCREEN,fill,cr,border_radius=S(18)); pygame.draw.rect(SCREEN,info["border"],cr,max(2,S(6)),border_radius=S(18))
                draw_text(item["name"].upper(),FONT_L if len(item["name"])<20 else FONT_M,info["border"],(cr.centerx,cr.y+S(52)),True)
                draw_text(item["en"],FONT_S,GRAY,(cr.centerx,cr.y+S(93)),True); draw_text(info["name"],FONT_M,info["border"],(cr.centerx,cr.bottom-S(38)),True)
            else: draw_text("ESCOLHA O SLOT E GIRE",FONT_M,DIVINE_BLUE,rr.center,True)
        SCREEN.set_clip(old_clip); draw_text("▼ RESULTADO ▼",FONT_S,YELLOW,(rr.centerx,rr.y+S(18)),True)
        roll=pygame.Rect(rr.x,rr.bottom+S(16),S(260),S(58)); auto=pygame.Rect(rr.x+S(278),rr.bottom+S(16),S(285),S(58)); config=pygame.Rect(rr.x+S(581),rr.bottom+S(16),S(369),S(58))
        roll_col=PANEL2 if self.passive_roll_spinning else (YELLOW if prof.get("points",0)>0 else PANEL2)
        pygame.draw.rect(SCREEN,roll_col,roll,border_radius=S(15)); draw_text("ROLANDO..." if self.passive_roll_spinning else "GIRAR - 1 PONTO",FONT_S,DARK if roll_col==YELLOW else WHITE,roll.center,True)
        pygame.draw.rect(SCREEN,GREEN if self.passive_auto_mode else PURPLE,auto,border_radius=S(15)); draw_text("AUTO: ON" if self.passive_auto_mode else "ROLAR AUTOMATICAMENTE",FONT_S,WHITE,auto.center,True)
        pygame.draw.rect(SCREEN,BLUE,config,border_radius=S(15)); draw_text("CONFIGURAR PARADA",FONT_S,WHITE,config.center,True)
        self.passive_roll_button=roll; self.passive_auto_button=auto; self.passive_auto_config_button=config
        catalog=pygame.Rect(CONTROL_SAFE_X,S(525),S(720),S(58)); pygame.draw.rect(SCREEN,DIVINE_BLUE,catalog,border_radius=S(14)); draw_text("VER PASSIVAS: VISTAS / TODAS",FONT_S,DARK,catalog.center,True); self.passive_roll_catalog_rect=catalog
        if self.passive_roll_message: draw_text(self.passive_roll_message,FONT_S,YELLOW,(W/2,H-CONTROL_SAFE_Y-S(105)),True)
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(50),S(210),S(48)); pygame.draw.rect(SCREEN,PANEL2,back,border_radius=S(12)); draw_text("VOLTAR",FONT_S,WHITE,back.center,True); self.passive_roll_back_rect=back
        self.passive_warning_yes_rect=pygame.Rect(0,0,0,0); self.passive_warning_no_rect=pygame.Rect(0,0,0,0)
        if self.passive_auto_warning:
            veil=pygame.Surface((W,H),pygame.SRCALPHA); veil.fill((0,0,0,190)); SCREEN.blit(veil,(0,0))
            box=pygame.Rect(W/2-S(650),H/2-S(190),S(1300),S(380)); pygame.draw.rect(SCREEN,PANEL,box,border_radius=S(24)); pygame.draw.rect(SCREEN,RED,box,max(2,S(5)),border_radius=S(24))
            draw_wrapped_text("Fei cê tem crtz? A passiva que tá equipada é uma das que ocê queria pegar, só avisando pô",FONT_M,WHITE,pygame.Rect(box.x+S(65),box.y+S(55),box.w-S(130),S(130)),3,True,3)
            yes=pygame.Rect(box.x+S(120),box.bottom-S(105),S(420),S(65)); no=pygame.Rect(box.right-S(540),box.bottom-S(105),S(420),S(65))
            pygame.draw.rect(SCREEN,RED,yes,border_radius=S(15)); pygame.draw.rect(SCREEN,GREEN,no,border_radius=S(15)); draw_text("MANDA BALA",FONT_M,WHITE,yes.center,True); draw_text("REAL PARCA",FONT_M,DARK,no.center,True)
            self.passive_warning_yes_rect=yes; self.passive_warning_no_rect=no

    def open_passive_dev(self):
        chars=[c for c in CHARACTER_ORDER if not is_beta_character(c)]
        if self.selected_character in chars:self.passive_dev_character=self.selected_character
        elif chars:self.passive_dev_character=chars[0]
        self.passive_dev_slot=0; self.passive_dev_page=0; self.state="passive_dev"

    def cycle_passive_dev_character(self,step):
        chars=[c for c in CHARACTER_ORDER if not is_beta_character(c)]
        if not chars:return
        try:i=chars.index(self.passive_dev_character)
        except ValueError:i=0
        self.passive_dev_character=chars[(i+step)%len(chars)]; self.passive_dev_page=0

    def draw_passive_dev(self):
        SCREEN.fill(BG); char=self.passive_dev_character; pp=passive_character_profile(char)
        draw_text("DEV | INJETOR DE PASSIVAS",FONT_L,RED,(W/2,S(48)),True)
        prev=pygame.Rect(W/2-S(560),S(82),S(100),S(46)); nxt=pygame.Rect(W/2+S(460),S(82),S(100),S(46))
        for r,l in ((prev,"<"),(nxt,">")):pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(11));draw_text(l,FONT_M,WHITE,r.center,True)
        draw_text(char.upper(),FONT_M,WHITE,(W/2,S(105)),True); self.passive_dev_char_prev_rect=prev; self.passive_dev_char_next_rect=nxt
        self.passive_dev_slot_rects=[]
        for i in range(2):
            r=pygame.Rect(CONTROL_SAFE_X+i*S(570),S(145),S(540),S(70)); k=pp["equipped"][i]; active=i==self.passive_dev_slot
            pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(13)); pygame.draw.rect(SCREEN,YELLOW if active else GRAY,r,max(2,S(4)),border_radius=S(13)); draw_text(f"SLOT {i+1}: "+(PASSIVE_BY_KEY[k]["name"] if k else "VAZIO"),FONT_S,WHITE,r.center,True); self.passive_dev_slot_rects.append(r)
        entries=list(PASSIVES); per=12; pages=max(1,math.ceil(len(entries)/per)); self.passive_dev_page=int(clamp(self.passive_dev_page,0,pages-1)); subset=entries[self.passive_dev_page*per:(self.passive_dev_page+1)*per]
        self.passive_dev_key_rects=[]; cols=4; gap=S(12); left=CONTROL_SAFE_X; top=S(245); cw=int((W-left*2-gap*3)/4); ch=S(115)
        for i,item in enumerate(subset):
            r=pygame.Rect(left+(i%cols)*(cw+gap),top+(i//cols)*(ch+S(10)),cw,ch); info=PASSIVE_RARITIES[item["rarity"]]
            pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(12)); pygame.draw.rect(SCREEN,info["border"],r,max(1,S(2)),border_radius=S(12)); draw_text(item["name"].upper(),FONT_S,info["border"],(r.centerx,r.y+S(32)),True); draw_text(info["name"],FONT_S,GRAY,(r.centerx,r.y+S(76)),True); self.passive_dev_key_rects.append((r,item["key"]))
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(50),S(210),S(48)); pprev=pygame.Rect(W/2-S(250),H-CONTROL_SAFE_Y-S(50),S(130),S(48)); pnxt=pygame.Rect(W/2+S(120),H-CONTROL_SAFE_Y-S(50),S(130),S(48)); clear=pygame.Rect(W-CONTROL_SAFE_X-S(250),H-CONTROL_SAFE_Y-S(50),S(250),S(48))
        for r,l in ((back,"VOLTAR"),(pprev,"<"),(pnxt,">"),(clear,"LIMPAR SLOT")):
            pygame.draw.rect(SCREEN,RED if l=="LIMPAR SLOT" else PANEL2,r,border_radius=S(12));draw_text(l,FONT_S,WHITE,r.center,True)
        draw_text(f"PAGINA {self.passive_dev_page+1}/{pages}",FONT_S,GRAY,(W/2,H-CONTROL_SAFE_Y-S(24)),True)
        self.passive_dev_back_rect=back; self.passive_dev_prev_rect=pprev; self.passive_dev_next_rect=pnxt; self.passive_dev_clear_rect=clear

    def draw_upgrade_catalog(self):
        SCREEN.fill(BG)
        draw_text("POWER UPS", FONT_L, WHITE, (W/2, S(48)), True)
        draw_text("TAGS INVISIVEIS IMPEDEM CARTAS INUTEIS PARA O PERSONAGEM", FONT_S, CYAN, (W/2, S(88)), True)

        tabs=[
            ("found","POWER UPS ENCONTRADOS"),
            ("all","TODOS OS POWER UPS"),
            ("synergies","SINERGIAS"),
            ("signatures","ESPECIFICOS DE PERSONAGENS"),
        ]
        margin=CONTROL_SAFE_X; gap=S(10); tw=int((W-margin*2-gap*3)/4); ty=S(112); th=S(52)
        self.upgrade_catalog_tab_rects=[]
        for i,(key,label) in enumerate(tabs):
            r=pygame.Rect(margin+i*(tw+gap),ty,tw,th); active=getattr(self,"upgrade_catalog_tab","found")==key
            pygame.draw.rect(SCREEN,CYAN if active else PANEL2,r,border_radius=S(12))
            pygame.draw.rect(SCREEN,WHITE if active else GRAY,r,max(1,S(2)),border_radius=S(12))
            draw_text(label,FONT_S,DARK if active else WHITE,r.center,True)
            self.upgrade_catalog_tab_rects.append((r,key))

        rarity_color = {"common":GRAY, "rare":BLUE, "epic":PURPLE, "legendary":YELLOW, "divine":DIVINE_BLUE, "cursed":RED}
        rarity_name = {"common":"COMUM", "rare":"RARO", "epic":"EPICO", "legendary":"LENDARIO", "divine":"DIVINO", "cursed":"AMALDICOADO"}
        per_page=6
        tab=getattr(self,"upgrade_catalog_tab","found")
        top=S(185); cols=2; gapc=S(18); card_w=int((W-SAFE*2-gapc)/2); card_h=S(205)

        if tab=="synergies":
            entries=list(UPGRADE_SYNERGIES)
            pages=max(1,math.ceil(max(1,len(entries))/per_page)); self.catalog_page=int(clamp(self.catalog_page,0,pages-1))
            subset=entries[self.catalog_page*per_page:(self.catalog_page+1)*per_page]
            for i,(req,name,desc) in enumerate(subset):
                col,row=i%cols,i//cols; r=pygame.Rect(SAFE+col*(card_w+gapc),top+row*(card_h+S(13)),card_w,card_h)
                pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(16)); pygame.draw.rect(SCREEN,YELLOW,r,max(2,S(3)),border_radius=S(16))
                draw_text("SINERGIA",FONT_S,YELLOW,(r.x+S(16),r.y+S(12)))
                draw_text(name,FONT_M,WHITE,(r.x+S(16),r.y+S(48)))
                names=[]
                by_key={card[3]:card[1] for _,card in self.all_upgrade_entries()}
                for key in sorted(req): names.append(by_key.get(key,key))
                draw_wrapped_text("REQUER: "+" + ".join(names),FONT_S,CYAN,pygame.Rect(r.x+S(16),r.y+S(90),r.w-S(32),S(45)),2,False,2)
                draw_wrapped_text(desc,FONT_S,GRAY,pygame.Rect(r.x+S(16),r.y+S(140),r.w-S(32),S(50)),2,False,2)
            count=len(entries)
        else:
            entries=self.upgrade_catalog_entries()
            pages=max(1,math.ceil(max(1,len(entries))/per_page)); self.catalog_page=int(clamp(self.catalog_page,0,pages-1))
            subset=entries[self.catalog_page*per_page:(self.catalog_page+1)*per_page]
            if tab=="found" and not subset:
                draw_text("NENHUM POWER UP ENCONTRADO AINDA",FONT_M,GRAY,(W/2,H*0.46),True)
                draw_text("Eles aparecem aqui assim que surgirem numa escolha de wave.",FONT_S,GRAY,(W/2,H*0.52),True)
            for i,(source,card) in enumerate(subset):
                rarity,name,desc,key=card; col,row=i%cols,i//cols; r=pygame.Rect(SAFE+col*(card_w+gapc),top+row*(card_h+S(13)),card_w,card_h)
                color=rarity_color.get(rarity,WHITE)
                pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(16)); pygame.draw.rect(SCREEN,color,r,max(2,S(3)),border_radius=S(16))
                draw_text(f"{source} | {rarity_name.get(rarity,rarity.upper())}",FONT_S,color,(r.x+S(16),r.y+S(12)))
                draw_text(name,FONT_M,WHITE,(r.x+S(16),r.y+S(50)))
                draw_wrapped_text(desc,FONT_S,GRAY,pygame.Rect(r.x+S(16),r.y+S(100),r.w-S(32),S(78)),3,False,3)
            count=len(entries)

        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(52),S(210),S(52)); prev=pygame.Rect(W/2-S(260),H-CONTROL_SAFE_Y-S(52),S(210),S(52)); nxt=pygame.Rect(W/2+S(50),H-CONTROL_SAFE_Y-S(52),S(210),S(52))
        for r,label in ((back,"VOLTAR"),(prev,"< ANTERIOR"),(nxt,"PROXIMA >")):
            pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(14)); draw_text(label,FONT_S,WHITE,r.center,True)
        draw_text(f"PAGINA {self.catalog_page+1}/{pages} | {count} ITENS",FONT_S,GRAY,(W/2,H-CONTROL_SAFE_Y-S(26)),True)
        self.catalog_back_rect,self.catalog_prev_rect,self.catalog_next_rect=back,prev,nxt

    def _draw_simple_back(self, title):
        SCREEN.fill(BG); draw_text(title,FONT_L,WHITE,(W/2,S(55)),True)
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(58),S(220),S(52)); pygame.draw.rect(SCREEN,PANEL2,back,border_radius=S(13)); draw_text("VOLTAR",FONT_S,WHITE,back.center,True)
        return back

    def draw_items(self):
        self.items_back_rect=self._draw_simple_back("ITENS DA FORJA")
        draw_text("Materiais e Pedacos dos Pecados agora ficam separados",FONT_S,GRAY,(W/2,S(102)),True)

        tab_w=S(330); tab_h=S(52); gap=S(20); ty=S(125)
        self.items_material_tab_rect=pygame.Rect(W/2-tab_w-gap/2,ty,tab_w,tab_h)
        self.items_sin_tab_rect=pygame.Rect(W/2+gap/2,ty,tab_w,tab_h)
        for r,label,active in [(self.items_material_tab_rect,"MATERIAIS",self.items_tab=="materials"),(self.items_sin_tab_rect,"PEDACOS DOS PECADOS",self.items_tab=="sins")]:
            pygame.draw.rect(SCREEN,CYAN if active else PANEL2,r,border_radius=S(13))
            pygame.draw.rect(SCREEN,WHITE if active else GRAY,r,max(1,S(2)),border_radius=S(13))
            draw_text(label,FONT_S,DARK if active else WHITE,r.center,True)

        if self.items_tab=="sins":
            keys=list(SIN_FRAGMENTS.keys())
            per=4
        else:
            keys=[k for k in FORGE_MATERIALS if k not in SIN_FRAGMENTS]
            per=5
        pages=max(1,math.ceil(len(keys)/per)); self.items_page%=pages
        y=S(200); self.items_rows=[]
        for key in keys[self.items_page*per:(self.items_page+1)*per]:
            info=FORGE_MATERIALS[key]; rarity_name,color=FORGE_RARITIES[info["rarity"]]; amount=self.forge_material_amount(key)
            r=pygame.Rect(CONTROL_SAFE_X,y,W-CONTROL_SAFE_X*2,S(104)); pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(14)); pygame.draw.rect(SCREEN,color,r,max(2,S(3)),border_radius=S(14))
            draw_text(f"{info['name']}  x{amount}",FONT_M,color,(r.x+S(18),r.y+S(10)))
            uses=[w["name"] for w in FORGE_WEAPONS if key in w["cost"]]
            draw_text(f"{rarity_name} | {info['desc']}",FONT_S,WHITE,(r.x+S(18),r.y+S(49)))
            draw_wrapped_text("USA EM: "+(" | ".join(uses) if uses else "nenhuma receita"),FONT_S,GRAY,pygame.Rect(r.x+S(18),r.y+S(75),r.w-S(36),S(28)),0,False,1)
            y += S(114)

        by=H-CONTROL_SAFE_Y-S(52)
        self.items_prev_rect=pygame.Rect(W/2-S(260),by,S(210),S(48))
        self.items_next_rect=pygame.Rect(W/2+S(50),by,S(210),S(48))
        if pages>1:
            for r,label in [(self.items_prev_rect,"< ANTERIOR"),(self.items_next_rect,"PROXIMA >")]:
                pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(13)); draw_text(label,FONT_S,WHITE,r.center,True)
        draw_text(f"PAGINA {self.items_page+1}/{pages}",FONT_S,GRAY,(W/2,by-S(28)),True)

    def _forge_character_weapons(self, character):
        return [w for w in FORGE_WEAPONS if w.get("character") == character]

    def _draw_forge_character_selector(self, selected_index, y):
        count = len(FORGE_CHARACTER_ORDER)
        selected_index %= max(1, count)
        char = FORGE_CHARACTER_ORDER[selected_index]
        prev = pygame.Rect(SAFE, y, S(120), S(54))
        nxt = pygame.Rect(W-SAFE-S(120), y, S(120), S(54))
        center = pygame.Rect(prev.right+S(16), y, nxt.x-prev.right-S(32), S(54))
        for r,label in ((prev,"<"),(nxt,">")):
            pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(12)); draw_text(label,FONT_M,WHITE,r.center,True)
        pygame.draw.rect(SCREEN,PANEL,center,border_radius=S(12)); pygame.draw.rect(SCREEN,CHARACTER_CONFIG[char]["color"],center,max(2,S(3)),border_radius=S(12))
        draw_text(char.upper(),FONT_M,WHITE,center.center,True)
        return char, prev, nxt

    def draw_weapons(self):
        self.weapons_back_rect=self._draw_simple_back("ARMAS")
        draw_text("ARSENAL SEPARADO POR PERSONAGEM",FONT_S,GRAY,(W/2,S(103)),True)
        char, self.weapons_char_prev_rect, self.weapons_char_next_rect = self._draw_forge_character_selector(self.weapons_character_index, S(126))
        entries=self._forge_character_weapons(char)
        per=3; pages=max(1,math.ceil(len(entries)/per)); self.weapons_page%=pages; self.weapon_equip_rects=[]
        y=S(198); crafted=set(SAVE.get("crafted_weapons",[])); eq=SAVE.get("equipped_weapons",{}) if isinstance(SAVE.get("equipped_weapons",{}),dict) else {}
        for w in entries[self.weapons_page*per:(self.weapons_page+1)*per]:
            rn,color=FORGE_RARITIES[w["rarity"]]; owned=w["key"] in crafted; equipped=eq.get(w["character"])==w["key"]
            r=pygame.Rect(SAFE,y,W-SAFE*2,S(146)); pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(14)); pygame.draw.rect(SCREEN,color,r,max(2,S(3)),border_radius=S(14))
            draw_text(f"{w['name']}  [{rn}]",FONT_M,color,(r.x+S(18),r.y+S(12)))
            draw_wrapped_text(w["desc"],FONT_S,GRAY,pygame.Rect(r.x+S(18),r.y+S(58),r.w-S(380),S(70)),2,False,3)
            preview=w.get("preview",False); testable=bool(preview and w.get("testable",False)); b=pygame.Rect(r.right-S(330),r.y+S(40),S(295),S(66)); bc=GREEN if (testable and equipped) else (DIVINE_BLUE if preview else (GREEN if equipped else (BLUE if owned else PANEL2))); pygame.draw.rect(SCREEN,bc,b,border_radius=S(14)); label=("BETA EQUIPADA" if testable and equipped else ("TESTAR BETA" if testable else ("PREVIA BETA" if preview else ("EQUIPADA" if equipped else ("EQUIPAR" if owned else "NAO FABRICADA"))))); draw_text(label,FONT_S,DARK if bc in (GREEN,BLUE,DIVINE_BLUE) else WHITE,b.center,True)
            if (testable and not equipped) or (owned and not equipped and not preview): self.weapon_equip_rects.append((b,w["key"]))
            y+=S(160)
        prev=pygame.Rect(W/2-S(330),H-CONTROL_SAFE_Y-S(58),S(180),S(52)); nxt=pygame.Rect(W/2+S(150),H-CONTROL_SAFE_Y-S(58),S(180),S(52))
        for r,l in [(prev,"< PAG"),(nxt,"PAG >")]: pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(12)); draw_text(l,FONT_S,WHITE,r.center,True)
        draw_text(f"{char} | PAGINA {self.weapons_page+1}/{pages} | {len(entries)} ARMAS",FONT_S,GRAY,(W/2,H-CONTROL_SAFE_Y-S(30)),True)
        self.weapons_prev_rect,self.weapons_next_rect=prev,nxt

    def draw_forge(self):
        self.forge_back_rect=self._draw_simple_back("FORJA")
        draw_text(f"MOEDAS: {SAVE.get('coins',0)} | ESCOLHA UM PERSONAGEM",FONT_S,GRAY,(W/2,S(103)),True)
        char, self.forge_char_prev_rect, self.forge_char_next_rect = self._draw_forge_character_selector(self.forge_character_index, S(126))
        entries=self._forge_character_weapons(char)
        per=3; pages=max(1,math.ceil(len(entries)/per)); self.forge_page%=pages; self.forge_recipe_rects=[]
        y=S(198); crafted=set(SAVE.get("crafted_weapons",[])); eq=SAVE.get("equipped_weapons",{}) if isinstance(SAVE.get("equipped_weapons",{}),dict) else {}
        for w in entries[self.forge_page*per:(self.forge_page+1)*per]:
            rn,color=FORGE_RARITIES[w["rarity"]]; owned=w["key"] in crafted; equipped=eq.get(w["character"])==w["key"]
            r=pygame.Rect(SAFE,y,W-SAFE*2,S(164)); pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(14)); pygame.draw.rect(SCREEN,color,r,max(2,S(3)),border_radius=S(14))
            draw_text(f"{w['name']}  [{rn}]",FONT_M,color,(r.x+S(18),r.y+S(10)))
            draw_wrapped_text(w["desc"],FONT_S,WHITE,pygame.Rect(r.x+S(18),r.y+S(52),r.w-S(400),S(44)),1,False,2)
            preview=w.get("preview",False); testable=bool(preview and w.get("testable",False))
            cost_txt=("BETA TESTAVEL | SEM CUSTO DURANTE OS TESTES" if testable else f"{w['coins']} moedas | "+"  ".join(f"{FORGE_MATERIALS[k]['name']} {self.forge_material_amount(k)}/{v}" for k,v in w["cost"].items()))
            draw_wrapped_text(cost_txt,FONT_S,DIVINE_BLUE if testable else GRAY,pygame.Rect(r.x+S(18),r.y+S(106),r.w-S(400),S(48)),1,False,2)
            b=pygame.Rect(r.right-S(345),r.y+S(48),S(310),S(68)); bc=GREEN if (testable and equipped) else (DIVINE_BLUE if preview else (GREEN if equipped else (BLUE if owned else ORANGE))); pygame.draw.rect(SCREEN,bc,b,border_radius=S(15)); label=("BETA EQUIPADA" if testable and equipped else ("TESTAR BETA" if testable else ("EM BETA" if preview else ("EQUIPADA" if equipped else ("EQUIPAR" if owned else "FABRICAR"))))); draw_text(label,FONT_S,DARK,b.center,True)
            if testable and not equipped: self.forge_recipe_rects.append((b,w["key"],True))
            elif not equipped and not preview: self.forge_recipe_rects.append((b,w["key"],owned))
            y+=S(178)
        prev=pygame.Rect(W/2-S(330),H-CONTROL_SAFE_Y-S(58),S(180),S(52)); nxt=pygame.Rect(W/2+S(150),H-CONTROL_SAFE_Y-S(58),S(180),S(52))
        for r,l in [(prev,"< PAG"),(nxt,"PAG >")]: pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(12)); draw_text(l,FONT_S,WHITE,r.center,True)
        draw_text(f"{char} | PAGINA {self.forge_page+1}/{pages}",FONT_S,GRAY,(W/2,H-CONTROL_SAFE_Y-S(30)),True)
        self.forge_prev_rect,self.forge_next_rect=prev,nxt

    def draw_bestiary(self):
        SCREEN.fill(BG)
        draw_text("BESTIARIO", FONT_L, WHITE, (W/2, S(58)), True)
        draw_text("TREINE CONTRA INIMIGOS, BOSSES E PECADOS",FONT_S,CYAN,(W/2,S(100)),True)
        per_page = 6
        visible_entries=[item for item in BESTIARY_ENTRIES if not item.get("hidden_key") or SAVE.get(item.get("hidden_key"),False)]
        pages = max(1, math.ceil(len(visible_entries)/per_page))
        self.bestiary_page = int(clamp(self.bestiary_page, 0, pages-1))
        subset = visible_entries[self.bestiary_page*per_page:(self.bestiary_page+1)*per_page]
        cols, gap = 2, S(22)
        top = S(120)
        card_w = int((W-SAFE*2-gap)/2)
        card_h = S(230)
        self.bestiary_train_rects=[]
        for i, item in enumerate(subset):
            col, row = i%cols, i//cols
            r = pygame.Rect(SAFE+col*(card_w+gap), top+row*(card_h+gap), card_w, card_h)
            boss = item["type"] == "Boss"
            if str(item.get("name","")).lower().startswith("glonk"):
                color=GREEN
            else:
                color = RED if boss else (YELLOW if item["type"] == "Mutacao" else ORANGE)
            pygame.draw.rect(SCREEN, PANEL, r, border_radius=S(18))
            pygame.draw.rect(SCREEN, color, r, width=max(2,S(4)), border_radius=S(18))
            draw_text(item["name"], FONT_M, color, (r.x+S(18), r.y+S(14)))
            draw_text(f"{item['type']} | HP {item['hp']}", FONT_S, WHITE, (r.x+S(18), r.y+S(62)))
            draw_text(f"VEL {item['speed']} | DANO {item['damage']}", FONT_S, GRAY, (r.x+S(18), r.y+S(98)))
            trainable=not str(item["type"]).lower().startswith("invocacao")
            draw_wrapped_text(item["desc"], FONT_S, GRAY, pygame.Rect(r.x+S(18), r.y+S(137), r.w-S(220 if trainable else 36), S(74)), 2, False, 2)
            if trainable:
                tr=pygame.Rect(r.right-S(182),r.bottom-S(60),S(160),S(44)); pygame.draw.rect(SCREEN,CYAN,tr,border_radius=S(12)); draw_text("TREINAR",FONT_S,DARK,tr.center,True); self.bestiary_train_rects.append((tr,item))
        draw_text(f"PAGINA {self.bestiary_page+1}/{pages}", FONT_S, GRAY, (W/2, H-S(48)), True)
        back = pygame.Rect(CONTROL_SAFE_X, H-CONTROL_SAFE_Y-S(52), S(210), S(52))
        prev = pygame.Rect(W/2-S(260), H-CONTROL_SAFE_Y-S(52), S(210), S(52))
        nxt = pygame.Rect(W/2+S(50), H-CONTROL_SAFE_Y-S(52), S(210), S(52))
        for r,label in [(back,"VOLTAR"),(prev,"< ANTERIOR"),(nxt,"PROXIMA >")]:
            pygame.draw.rect(SCREEN, PANEL2, r, border_radius=S(14)); draw_text(label, FONT_S, WHITE, r.center, True)
        self.bestiary_back_rect, self.bestiary_prev_rect, self.bestiary_next_rect = back, prev, nxt

    def draw_control_editor(self):
        self.draw_bg()
        draw_text("EDITOR DE CONTROLES", FONT_L, WHITE, (W/2, S(52)), True)
        draw_text("ARRASTE QUALQUER BOTAO. O LAYOUT E SALVO AUTOMATICAMENTE.", FONT_S, GRAY, (W/2, S(104)), True)
        labels = {"joystick":"JOYSTICK", "attack":"ATK / MIRA", "dash":"DASH", "parry":"PARRY", "domain":"DOM", "pause":"PAUSE"}
        colors = {"attack":RED, "dash":CYAN, "parry":YELLOW, "domain":PURPLE, "pause":PANEL2}
        for key, rect in self.buttons.items():
            color = colors.get(key, PANEL2)
            pygame.draw.rect(SCREEN, color, rect, border_radius=S(18))
            pygame.draw.rect(SCREEN, WHITE, rect, width=max(2,S(3)), border_radius=S(18))
            draw_text(labels[key], FONT_S, DARK if color in (CYAN,YELLOW) else WHITE, rect.center, True)
        back = pygame.Rect(CONTROL_SAFE_X, H-CONTROL_SAFE_Y-S(50), S(210), S(50))
        reset = pygame.Rect(W/2-S(315), H-CONTROL_SAFE_Y-S(50), S(200), S(50))
        minus = pygame.Rect(W/2-S(90), H-CONTROL_SAFE_Y-S(50), S(160), S(50))
        plus = pygame.Rect(W/2+S(95), H-CONTROL_SAFE_Y-S(50), S(160), S(50))
        for r,label,c in [(back,"VOLTAR",PANEL2),(reset,"RESET",RED),(minus,"TAMANHO -",PANEL2),(plus,"TAMANHO +",BLUE)]:
            pygame.draw.rect(SCREEN,c,r,border_radius=S(13)); draw_text(label,FONT_S,WHITE,r.center,True)
        self.control_back_rect, self.control_reset_rect, self.control_minus_rect, self.control_plus_rect = back, reset, minus, plus

    def draw_run_upgrades(self):
        SCREEN.fill(BG)
        draw_text("UPGRADES DA RUN", FONT_L, WHITE, (W/2, S(58)), True)
        card_by_key = {card[3]:(source,card) for source,card in self.all_upgrade_entries()}
        entries = []
        for key, count in self.owned_upgrade_counts.items():
            if key in card_by_key:
                entries.append((card_by_key[key][0], card_by_key[key][1], count))
        entries.sort(key=lambda item: item[1][1])
        per_page = 8
        pages = max(1, math.ceil(max(1,len(entries))/per_page))
        self.run_upgrade_page = int(clamp(self.run_upgrade_page, 0, pages-1))
        subset = entries[self.run_upgrade_page*per_page:(self.run_upgrade_page+1)*per_page]
        if not subset:
            draw_text("NENHUM UPGRADE AINDA. SOBREVIVA MAIS UM POUCO, CHEFE.", FONT_M, GRAY, (W/2,H*0.43), True)
        else:
            cols, gap = 2, S(18)
            top, card_h = S(125), S(155)
            card_w = int((W-SAFE*2-gap)/2)
            rarity_color = {"common":GRAY, "rare":BLUE, "epic":PURPLE, "legendary":YELLOW, "divine":DIVINE_BLUE, "cursed":RED}
            for i,(source,card,count) in enumerate(subset):
                rarity,name,desc,key=card
                col,row=i%cols,i//cols
                r=pygame.Rect(SAFE+col*(card_w+gap),top+row*(card_h+gap),card_w,card_h)
                pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(16)); pygame.draw.rect(SCREEN,rarity_color[rarity],r,width=max(2,S(3)),border_radius=S(16))
                suffix=f" x{count}" if count>1 else ""
                draw_text(name+suffix,FONT_M,WHITE,(r.x+S(15),r.y+S(12)))
                draw_wrapped_text(desc,FONT_S,GRAY,pygame.Rect(r.x+S(15),r.y+S(57),r.w-S(30),S(78)),2,False,2)
        if self.synergies:
            draw_text("SINERGIAS: " + " | ".join(sorted(self.synergies)), FONT_S, YELLOW, (W/2,H-S(92)), True)
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(48),S(210),S(48)); prev=pygame.Rect(W/2-S(260),H-CONTROL_SAFE_Y-S(48),S(210),S(48)); nxt=pygame.Rect(W/2+S(50),H-CONTROL_SAFE_Y-S(48),S(210),S(48))
        for r,label in [(back,"VOLTAR AO PAUSE"),(prev,"< ANTERIOR"),(nxt,"PROXIMA >")]:
            pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(13)); draw_text(label,FONT_S,WHITE,r.center,True)
        self.run_upgrades_back_rect,self.run_upgrades_prev_rect,self.run_upgrades_next_rect=back,prev,nxt

    def draw_shop(self):
        SCREEN.fill(BG)
        draw_text("LOJA PERMANENTE", FONT_L, WHITE, (W/2, S(62)), True)
        draw_text(f"MOEDAS: {SAVE['coins']}", FONT_M, ORANGE, (W/2, S(112)), True)
        per_page = 6
        pages = max(1, math.ceil(len(PERMANENT_UPGRADES)/per_page))
        self.shop_page = int(clamp(self.shop_page, 0, pages-1))
        subset = PERMANENT_UPGRADES[self.shop_page*per_page:(self.shop_page+1)*per_page]
        self.shop_rects = []
        cols, gap = 2, S(18)
        top, card_h = S(160), S(190)
        card_w = int((W-SAFE*2-gap)/2)
        for i, (key, name, desc, base) in enumerate(subset):
            lvl = min(PERMANENT_UPGRADE_CAP, int(SAVE.get(key, 0)))
            cost = base + lvl * 35
            col, row = i%cols, i//cols
            r = pygame.Rect(SAFE+col*(card_w+gap), top+row*(card_h+gap), card_w, card_h)
            pygame.draw.rect(SCREEN, PANEL, r, border_radius=S(18))
            draw_text(f"{name}  LV.{lvl}", FONT_M, WHITE, (r.x+S(18), r.y+S(16)))
            draw_wrapped_text(desc, FONT_S, GRAY, pygame.Rect(r.x+S(18), r.y+S(68), r.w-S(220), S(80)), 2, False, 3)
            buy = pygame.Rect(r.right-S(185), r.y+S(55), S(160), S(78))
            capped=lvl>=PERMANENT_UPGRADE_CAP
            pygame.draw.rect(SCREEN, PANEL2 if capped else (ORANGE if SAVE['coins'] >= cost else PANEL2), buy, border_radius=S(16))
            draw_text("MAX LV.30" if capped else f"{cost} $", FONT_S, WHITE, buy.center, True)
            self.shop_rects.append((buy, key, cost, not capped))
        back = pygame.Rect(CONTROL_SAFE_X, H-CONTROL_SAFE_Y-S(50), S(210), S(50))
        prev = pygame.Rect(W/2-S(260), H-CONTROL_SAFE_Y-S(50), S(210), S(50))
        nxt = pygame.Rect(W/2+S(50), H-CONTROL_SAFE_Y-S(50), S(210), S(50))
        for r,label in [(back,"VOLTAR"),(prev,"< ANTERIOR"),(nxt,"PROXIMA >")]:
            pygame.draw.rect(SCREEN, PANEL2, r, border_radius=S(14)); draw_text(label,FONT_S,WHITE,r.center,True)
        draw_text(f"PAGINA {self.shop_page+1}/{pages}", FONT_S, GRAY, (W-S(180), H-S(48)), True)
        self.shop_back_rect, self.shop_prev_rect, self.shop_next_rect = back, prev, nxt

    def draw_upgrade(self):
        SCREEN.fill(BG)
        draw_text("ONDA CONCLUIDA", FONT_L, GREEN, (W/2, S(72)), True)
        draw_text("TOQUE EM UM BUFF E DEPOIS CONFIRME", FONT_M, WHITE, (W/2, S(125)), True)
        if self.unlock_notice_timer > 0:
            draw_text(self.unlock_notice, FONT_S, PURPLE, (W-S(320), S(82)), True)
        if self.evolution_notice_timer > 0 and self.evolution_notice:
            draw_text(self.evolution_notice, FONT_S, YELLOW, (W/2, S(158)), True)
        rarity_color = {"common": GRAY, "rare": BLUE, "epic": PURPLE, "legendary": YELLOW, "divine": DIVINE_BLUE, "cursed": RED}
        rarity_name = {"common": "COMUM", "rare": "RARO", "epic": "EPICO", "legendary": "LENDARIO", "divine":"DIVINO", "cursed": "AMALDICOADO"}
        self.upgrade_rects = []
        cols, gap = 3, S(18)
        card_w = int((W-SAFE*2-gap*2)/3)
        card_h = S(450)
        y = S(195) if self.evolution_notice_timer > 0 else S(180)
        for i, card in enumerate(self.upgrade_cards):
            rarity, name, desc, key = card
            r = pygame.Rect(SAFE+i*(card_w+gap), y, card_w, card_h)
            selected = self.selected_upgrade_card == card
            pygame.draw.rect(SCREEN, PANEL2 if selected else PANEL, r, border_radius=S(22))
            pygame.draw.rect(SCREEN, WHITE if selected else rarity_color[rarity], r, width=max(S(4), S(8) if selected else S(4)), border_radius=S(22))
            draw_text(rarity_name[rarity], FONT_S, rarity_color[rarity], (r.centerx, r.y+S(35)), True)
            draw_wrapped_text(name, FONT_M, WHITE, pygame.Rect(r.x+S(18),r.y+S(78),r.w-S(36),S(100)),3,True,2)
            draw_wrapped_text(desc, FONT_S, GRAY, pygame.Rect(r.x+S(18),r.y+S(190),r.w-S(36),S(150)),3,True,4)
            draw_text("SELECIONADO" if selected else "TOQUE PARA MARCAR", FONT_S, GREEN if selected else rarity_color[rarity], (r.centerx, r.bottom-S(44)), True)
            self.upgrade_rects.append((r, card))
        confirm = pygame.Rect(W/2-S(260), H-CONTROL_SAFE_Y-S(92), S(520), S(82))
        ready = self.selected_upgrade_card is not None
        pygame.draw.rect(SCREEN, GREEN if ready else PANEL2, confirm, border_radius=S(20))
        draw_text("CONFIRMAR BUFF" if ready else "ESCOLHA UM BUFF", FONT_M, DARK if ready else GRAY, confirm.center, True)
        self.upgrade_confirm_rect = confirm

    def draw_death(self):
        SCREEN.fill((24, 10, 14))
        if self.devoured_by_gula:
            draw_text("A GULA", FONT_XL, RED, (W/2, H*0.14), True)
            draw_wrapped_text("A Gula não te matou, ela devorou sua experiência.", FONT_M, WHITE,
                              pygame.Rect(W*0.16, H*0.20, W*0.68, S(100)), 4, True, 2)
            draw_text(f"FOME NA PROXIMA VEZ: {self.gula_death_hunger}", FONT_S, RED, (W/2, H*0.29), True)
        else:
            draw_text("VOCE MORREU", FONT_XL, RED, (W/2, H*0.16), True)
            draw_text("SEU HP CHEGOU A ZERO.", FONT_S, GRAY, (W/2, H*0.23), True)
        stats = [
            f"Personagem: {self.selected_character}",
            f"Onda alcancada: {self.wave}",
            f"Inimigos derrotados: {self.kills}",
            f"Tempo vivo: {self.final_time}s",
            f"Parries: {self.parries}",
            f"Perfect Dodges: {self.perfect_dodges}",
            f"Pontuacao: {self.score}",
            f"Moedas obtidas: {self.run_coins}",
        ]
        y = H*(0.35 if self.devoured_by_gula else 0.31)
        for s in stats:
            draw_text(s, FONT_M, WHITE, (W/2, y), True)
            y += S(52)
        retry = pygame.Rect(W/2-S(255), H*0.76, S(510), S(100))
        menu = pygame.Rect(W/2-S(255), H*0.84, S(510), S(90))
        pygame.draw.rect(SCREEN, RED, retry, border_radius=S(24))
        pygame.draw.rect(SCREEN, PANEL2, menu, border_radius=S(24))
        draw_text("TENTAR DE NOVO", FONT_M, WHITE, retry.center, True)
        draw_text("MENU", FONT_M, WHITE, menu.center, True)
        self.death_retry_rect = retry
        self.death_menu_rect = menu

    def pause_game(self):
        if self.state != "playing":
            return
        self.state = "paused"
        bw, bh = S(520), S(92)
        self.pause_resume_rect = pygame.Rect(W/2-bw/2, H*0.43, bw, bh)
        self.pause_menu_rect = pygame.Rect(W/2-bw/2, H*0.55, bw, bh)
        AUDIO.play("pause", 0.70)
        self.attack_held = False; self.parry_held=False; self.domain_held=False; self.dash_held=False
        for key in self.move_touch:
            self.move_touch[key] = False
        self.active_fingers.clear()
        self.joystick_finger = None
        self.joystick_mouse_active = False
        self.joystick_vector.update(0, 0)

    def draw_paused(self):
        self.draw_playing()
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 190))
        SCREEN.blit(overlay, (0, 0))
        draw_text("PAUSADO", FONT_XL, WHITE, (W*0.30, H*0.22), True)

        bw, bh = S(470), S(78)
        x = W*0.30-bw/2
        resume = pygame.Rect(x, H*0.34, bw, bh)
        upgrades = pygame.Rect(x, H*0.45, bw, bh)
        menu = pygame.Rect(x, H*0.56, bw, bh)
        pygame.draw.rect(SCREEN, CYAN, resume, border_radius=S(18))
        pygame.draw.rect(SCREEN, PURPLE, upgrades, border_radius=S(18))
        pygame.draw.rect(SCREEN, PANEL2, menu, border_radius=S(18))
        draw_text("CONTINUAR", FONT_M, DARK, resume.center, True)
        draw_text("UPGRADES DA RUN", FONT_M, WHITE, upgrades.center, True)
        draw_text("VOLTAR AO MENU", FONT_M, WHITE, menu.center, True)

        settings_btn = pygame.Rect(W*0.30-S(235), int(H*0.69), S(470), S(60))
        pygame.draw.rect(SCREEN, BLUE, settings_btn, border_radius=S(14))
        draw_text("CONFIGURACOES", FONT_S, WHITE, settings_btn.center, True)

        # Painel rapido: da pra ver imediatamente o que a build possui.
        panel = pygame.Rect(W*0.54, H*0.20, W*0.40, H*0.60)
        pygame.draw.rect(SCREEN, PANEL, panel, border_radius=S(20))
        pygame.draw.rect(SCREEN, WHITE, panel, width=max(2,S(3)), border_radius=S(20))
        draw_text(f"BUILD ATUAL - {self.player.character}", FONT_M, self.player.color, (panel.centerx, panel.y+S(38)), True)
        key_to_name = {card[3]:card[1] for _,card in self.all_upgrade_entries()}
        owned = [(key_to_name.get(k,k),c) for k,c in self.owned_upgrade_counts.items()]
        owned.sort()
        y = panel.y+S(82)
        if not owned:
            draw_text("Nenhum upgrade ainda", FONT_S, GRAY, (panel.centerx, y+S(30)), True)
        else:
            for name,count in owned[:7]:
                suffix=f" x{count}" if count>1 else ""
                draw_text("- "+name+suffix, FONT_S, WHITE, (panel.x+S(22), y))
                y += S(38)
            if len(owned)>7:
                draw_text(f"... e mais {len(owned)-7}", FONT_S, GRAY, (panel.x+S(22), y))
                y += S(38)
        if self.synergies:
            draw_text("SINERGIAS", FONT_S, YELLOW, (panel.x+S(22), panel.bottom-S(92)))
            draw_wrapped_text(" | ".join(sorted(self.synergies)), FONT_S, YELLOW, pygame.Rect(panel.x+S(22),panel.bottom-S(60),panel.w-S(44),S(55)),2,False,2)

        self.pause_resume_rect = resume
        self.pause_upgrades_rect = upgrades
        self.pause_menu_rect = menu
        self.pause_settings_rect = settings_btn

    def draw_whats_new(self):
        SCREEN.fill(BG)
        version = self.whats_new_version if self.whats_new_version in WHATS_NEW_BY_VERSION else "V15"
        entries = WHATS_NEW_BY_VERSION[version]
        draw_text(f"NOVIDADES - {version}", FONT_L, WHITE, (W/2, S(48)), True)
        draw_text("ARRASTE PARA CIMA/BAIXO | TOQUE NA VERSAO PARA ALTERNAR", FONT_S, CYAN, (W/2, S(88)), True)

        bw, bh, gap = S(180), S(50), S(14)
        total = bw*3 + gap*2
        x0 = W/2 - total/2
        v13 = pygame.Rect(x0, S(108), bw, bh)
        v14 = pygame.Rect(x0+bw+gap, S(108), bw, bh)
        v15 = pygame.Rect(x0+(bw+gap)*2, S(108), bw, bh)
        for rect,key in ((v13,"V13"),(v14,"V14"),(v15,"V15")):
            active = key == version
            pygame.draw.rect(SCREEN, DIVINE_BLUE if active else PANEL2, rect, border_radius=S(13))
            pygame.draw.rect(SCREEN, WHITE if active else GRAY, rect, width=max(1,S(2)), border_radius=S(13))
            draw_text(key, FONT_M, DARK if active else WHITE, rect.center, True)
        self.whats_new_v13_rect=v13; self.whats_new_v14_rect=v14; self.whats_new_v15_rect=v15

        viewport=pygame.Rect(CONTROL_SAFE_X,S(176),W-CONTROL_SAFE_X*2,H-S(278))
        pygame.draw.rect(SCREEN,(20,21,29),viewport,border_radius=S(16))
        card_h=S(118); gap_y=S(12)
        content_h=len(entries)*(card_h+gap_y)+S(8)
        max_scroll=max(0,content_h-viewport.h)
        self.whats_new_max_scroll=max_scroll
        self.whats_new_scroll=clamp(self.whats_new_scroll,-self.whats_new_overscroll,max_scroll+self.whats_new_overscroll)
        old_clip=SCREEN.get_clip(); SCREEN.set_clip(viewport)
        y=viewport.y+S(8)-self.whats_new_scroll
        for i,line in enumerate(entries):
            r=pygame.Rect(viewport.x+S(10),int(y),viewport.w-S(20),card_h)
            if r.bottom>=viewport.top and r.top<=viewport.bottom:
                edge=DIVINE_BLUE if version in ("V14","V15") else CYAN
                pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(14))
                pygame.draw.rect(SCREEN,edge,r,width=max(1,S(2)),border_radius=S(14))
                draw_text(str(i+1),FONT_M,YELLOW,(r.x+S(22),r.centery),True)
                draw_wrapped_text(line,FONT_S,WHITE,pygame.Rect(r.x+S(58),r.y+S(18),r.w-S(78),r.h-S(30)),2,False,3)
            y += card_h+gap_y
        SCREEN.set_clip(old_clip)
        if max_scroll>0:
            track=pygame.Rect(viewport.right-S(10),viewport.y+S(8),S(5),viewport.h-S(16)); pygame.draw.rect(SCREEN,PANEL2,track,border_radius=S(3))
            knob_h=max(S(35),int(track.h*viewport.h/max(content_h,1)))
            visual_scroll=clamp(self.whats_new_scroll,0,max_scroll)
            knob_y=track.y+(track.h-knob_h)*(visual_scroll/max_scroll)
            pygame.draw.rect(SCREEN,DIVINE_BLUE if version in ("V14","V15") else CYAN,(track.x,knob_y,track.w,knob_h),border_radius=S(3))
        back = pygame.Rect(CONTROL_SAFE_X, H-CONTROL_SAFE_Y-S(46), S(210), S(46))
        pygame.draw.rect(SCREEN, PANEL2, back, border_radius=S(14)); draw_text("VOLTAR", FONT_S, WHITE, back.center, True)
        self.whats_new_back_rect = back
        self.whats_new_viewport=viewport

    def set_whats_new_version(self, version):
        if version in WHATS_NEW_BY_VERSION and version != self.whats_new_version:
            self.whats_new_version=version
            self.whats_new_scroll=0.0
            self.whats_new_drag_start=None
            AUDIO.play("click",0.45)

    def whats_new_down(self,pos):
        if self.whats_new_back_rect.collidepoint(pos):
            self.state="menu"; return
        if self.whats_new_v13_rect.collidepoint(pos):
            self.set_whats_new_version("V13"); return
        if self.whats_new_v14_rect.collidepoint(pos):
            self.set_whats_new_version("V14"); return
        if self.whats_new_v15_rect.collidepoint(pos):
            self.set_whats_new_version("V15"); return
        if self.whats_new_viewport.collidepoint(pos):
            self.whats_new_drag_start=pygame.Vector2(pos)
            self.whats_new_scroll_start=self.whats_new_scroll

    def whats_new_motion(self,pos):
        if self.whats_new_drag_start is None: return
        dy=pygame.Vector2(pos).y-self.whats_new_drag_start.y
        raw=self.whats_new_scroll_start-dy; mx=max(0.0,self.whats_new_max_scroll)
        if raw<0: raw*=0.34
        elif raw>mx: raw=mx+(raw-mx)*0.34
        self.whats_new_scroll=clamp(raw,-self.whats_new_overscroll,mx+self.whats_new_overscroll)

    def whats_new_up(self,pos=None):
        self.whats_new_drag_start=None

    def update_whats_new_scroll(self,dt):
        if self.whats_new_drag_start is not None: return
        target=clamp(self.whats_new_scroll,0,max(0.0,self.whats_new_max_scroll))
        if abs(self.whats_new_scroll-target)<0.35: self.whats_new_scroll=target; return
        self.whats_new_scroll += (target-self.whats_new_scroll)*min(1.0,12.0*dt)

    def _settings_percent(self, kind):
        if kind == "music": return int(round(AUDIO.music_volume*100))
        return int(round(AUDIO.sfx_volume*100))

    def _settings_set_from_x(self, kind, x):
        track = self.settings_music_track if kind == "music" else self.settings_sfx_track
        pct = int(round(clamp((x-track.x)/max(1,track.w),0.0,1.0)*100))
        if kind == "music":
            AUDIO.set_music_volume(pct); SAVE["music_volume"]=pct; SAVE["music_on"]=pct>0
        else:
            AUDIO.set_sfx_volume(pct); SAVE["sfx_volume"]=pct; SAVE["sfx_on"]=pct>0
        self.settings_dirty=True

    def open_settings(self, return_state="menu"):
        self.settings_return_state = return_state if return_state in ("menu","paused") else "menu"
        self.settings_drag=None
        self.settings_dirty=False
        self.state="settings"

    def close_settings(self):
        if self.settings_dirty:
            save_data(SAVE)
            self.settings_dirty=False
        self.settings_drag=None
        self.state=self.settings_return_state

    def draw_settings(self):
        SCREEN.fill(BG)
        draw_text("CONFIGURACOES",FONT_XL,WHITE,(W/2,S(90)),True)
        draw_text("AUDIO",FONT_M,DIVINE_BLUE,(W/2,S(155)),True)
        panel=pygame.Rect(W/2-S(600),S(205),S(1200),S(500))
        pygame.draw.rect(SCREEN,PANEL,panel,border_radius=S(24)); pygame.draw.rect(SCREEN,WHITE,panel,max(2,S(3)),border_radius=S(24))
        left=panel.x+S(110); right=panel.right-S(110); track_w=right-left
        rows=[("music","MUSICA",S(330),DIVINE_BLUE),("sfx","EFEITOS",S(520),YELLOW)]
        for kind,label,y,color in rows:
            pct=self._settings_percent(kind)
            draw_text(label,FONT_M,WHITE,(left,y-S(60)))
            draw_text(f"{pct}%",FONT_M,color,(right,y-S(60)),True)
            track=pygame.Rect(left,y,track_w,S(22))
            pygame.draw.rect(SCREEN,PANEL2,track,border_radius=S(11))
            fill=track.copy(); fill.w=int(track.w*pct/100)
            pygame.draw.rect(SCREEN,color,fill,border_radius=S(11))
            knob_x=track.x+int(track.w*pct/100)
            pygame.draw.circle(SCREEN,WHITE,(knob_x,track.centery),S(23))
            pygame.draw.circle(SCREEN,color,(knob_x,track.centery),S(15))
            hit=track.inflate(S(40),S(55))
            if kind=="music": self.settings_music_track=track; self.settings_music_hit=hit
            else: self.settings_sfx_track=track; self.settings_sfx_hit=hit
        draw_text("ARRASTE AS BARRAS | 0% = MUDO | 100% = MAXIMO",FONT_S,GRAY,(W/2,panel.bottom-S(58)),True)
        back=pygame.Rect(W/2-S(210),H-CONTROL_SAFE_Y-S(72),S(420),S(62))
        pygame.draw.rect(SCREEN,PANEL2,back,border_radius=S(16)); draw_text("SALVAR E VOLTAR",FONT_S,WHITE,back.center,True)
        self.settings_back_rect=back

    def settings_down(self,pos):
        if self.settings_back_rect.collidepoint(pos):
            self.close_settings(); return
        if self.settings_music_hit.collidepoint(pos):
            self.settings_drag="music"; self._settings_set_from_x("music",pos[0]); return
        if self.settings_sfx_hit.collidepoint(pos):
            self.settings_drag="sfx"; self._settings_set_from_x("sfx",pos[0]); return

    def settings_motion(self,pos):
        if self.settings_drag:
            self._settings_set_from_x(self.settings_drag,pos[0])

    def settings_up(self,pos=None):
        if self.settings_drag is not None:
            self.settings_drag=None
            save_data(SAVE); self.settings_dirty=False

    def draw_achievements(self):
        SCREEN.fill(BG)
        unlocked=set(SAVE.get("unlocked_achievements",[])); known={a[0] for a in ACHIEVEMENTS}; unlocked_now=unlocked&known
        per_page=6; pages=max(1,math.ceil(len(ACHIEVEMENTS)/per_page)); self.achievement_page=int(clamp(self.achievement_page,0,pages-1))
        subset=ACHIEVEMENTS[self.achievement_page*per_page:(self.achievement_page+1)*per_page]
        draw_text("CONQUISTAS",FONT_L,WHITE,(W/2,S(48)),True)
        normal_keys=[a[0] for a in ACHIEVEMENTS if a[0]!="meta_all"]; done=sum(1 for k in normal_keys if k in unlocked); pct=int(round(100*done/max(1,len(normal_keys))))
        draw_text(f"{len(unlocked_now)}/{len(ACHIEVEMENTS)}  |  PAGINA {self.achievement_page+1}/{pages}  |  TOTAL {pct}%",FONT_S,YELLOW,(W/2,S(88)),True)
        topbar=pygame.Rect(W/2-S(330),S(108),S(660),S(16)); pygame.draw.rect(SCREEN,PANEL2,topbar,border_radius=S(8)); fill=topbar.copy(); fill.w=int(topbar.w*pct/100); pygame.draw.rect(SCREEN,DIVINE_BLUE,fill,border_radius=S(8))
        cols=2; gap=S(16); top=S(140); card_h=S(172); card_w=int((W-CONTROL_SAFE_X*2-gap)/2)
        for i,(key,name,desc) in enumerate(subset):
            col,row=i%cols,i//cols; r=pygame.Rect(CONTROL_SAFE_X+col*(card_w+gap),top+row*(card_h+gap),card_w,card_h)
            ok=key in unlocked; rarity=achievement_rarity(key); special=rarity=="meta"; edge=ACHIEVEMENT_RARITY_COLORS[rarity]
            pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(15)); pygame.draw.rect(SCREEN,edge,r,width=max(2,S(4 if special else 3)),border_radius=S(15))
            draw_text(("[OK] " if ok else "[ ] ")+name,FONT_M,edge,(r.x+S(14),r.y+S(12)))
            draw_text(ACHIEVEMENT_RARITY_NAMES[rarity],FONT_S,edge,(r.centerx,r.y+S(48)),True)
            draw_wrapped_text(desc,FONT_S,WHITE if ok else GRAY,pygame.Rect(r.x+S(14),r.y+S(72),r.w-S(28),S(48)),2,False,2)
            cur,goal,pp=self.achievement_progress(key); bar=pygame.Rect(r.x+S(14),r.bottom-S(38),r.w-S(28),S(12)); pygame.draw.rect(SCREEN,DARK,bar,border_radius=S(6)); f=bar.copy(); f.w=int(bar.w*pp/100); pygame.draw.rect(SCREEN,edge,f,border_radius=S(6))
            txt=f"{int(pp)}%" if goal<=1 else f"{min(cur,goal)}/{goal}  ({int(pp)}%)"
            draw_text(txt,FONT_S,WHITE,(r.centerx,r.bottom-S(19)),True)
        yb=H-CONTROL_SAFE_Y-S(50); back=pygame.Rect(CONTROL_SAFE_X,yb,S(210),S(48)); prev=pygame.Rect(W/2-S(260),yb,S(210),S(48)); nxt=pygame.Rect(W/2+S(50),yb,S(210),S(48))
        for r,label in [(back,"VOLTAR"),(prev,"< ANTERIOR"),(nxt,"PROXIMA >")]: pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(13)); draw_text(label,FONT_S,WHITE,r.center,True)
        self.achievements_back_rect=back; self.achievements_prev_rect=prev; self.achievements_next_rect=nxt

    def draw_missions(self):
        SCREEN.fill(BG)
        chars=list(CHARACTER_MISSIONS.keys())
        self.mission_character_index %= len(chars)
        char=chars[self.mission_character_index]
        stats=self.mission_stats_for(char)
        completed=set(SAVE.get("completed_missions", []))
        draw_text("MISSOES POR PERSONAGEM",FONT_L,WHITE,(W/2,S(58)),True)
        draw_text(char.upper(),FONT_M,CHARACTER_CONFIG[char]["color"],(W/2,S(112)),True)
        missions=CHARACTER_MISSIONS[char]
        y=S(180)
        for mission_id,name,desc,stat_key,goal,reward in missions:
            r=pygame.Rect(S(130),y,W-S(260),S(190)); ok=mission_id in completed
            current=min(goal,stats.get(stat_key,0))
            pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(18)); pygame.draw.rect(SCREEN,GREEN if ok else PURPLE,r,width=max(2,S(4)),border_radius=S(18))
            draw_text(name,FONT_M,GREEN if ok else WHITE,(r.x+S(22),r.y+S(18)))
            draw_text(desc,FONT_S,GRAY,(r.x+S(22),r.y+S(72)))
            draw_text(("CONCLUIDA" if ok else f"PROGRESSO {current}/{goal}")+f"   |   RECOMPENSA {reward} MOEDAS",FONT_S,YELLOW,(r.x+S(22),r.y+S(125)))
            y += S(215)
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(50),S(210),S(50)); prev=pygame.Rect(W/2-S(300),H-CONTROL_SAFE_Y-S(50),S(240),S(50)); nxt=pygame.Rect(W/2+S(60),H-CONTROL_SAFE_Y-S(50),S(240),S(50))
        for r,label in [(back,"VOLTAR"),(prev,"< PERSONAGEM"),(nxt,"PERSONAGEM >")]: pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(13)); draw_text(label,FONT_S,WHITE,r.center,True)
        self.missions_back_rect,self.missions_prev_rect,self.missions_next_rect=back,prev,nxt

    def draw_cheats(self):
        SCREEN.fill(BG)
        money_unlocked = SAVE.get("cheat_money", False)
        mode_names={"wave":"ONDA INICIAL","evo":"PONTOS DE EVOLUCAO"}
        title = ("CHEAT: DINHEIRO" if self.cheat_money_mode else ("CHEAT: "+mode_names.get(self.cheat_value_mode,"") if self.cheat_value_mode else "AREA DE CHEAT"))
        subtitle = ("DIGITE QUANTO DINHEIRO VOCE QUER" if self.cheat_money_mode else
                    ("DIGITE O VALOR E CONFIRME" if self.cheat_value_mode else "DIGITE O CODIGO DE TESTE"))
        draw_text(title, FONT_L, WHITE, (W/2,S(60)), True)
        draw_text(subtitle, FONT_S, GRAY, (W/2,S(112)), True)
        box=pygame.Rect(W/2-S(300),S(155),S(600),S(85)); pygame.draw.rect(SCREEN,PANEL,box,border_radius=S(18)); pygame.draw.rect(SCREEN,PURPLE,box,width=max(2,S(4)),border_radius=S(18))
        numeric_mode = self.cheat_money_mode or self.cheat_value_mode in ("wave","evo")
        buffer = self.cheat_money_buffer if numeric_mode else self.cheat_buffer
        shown = buffer if numeric_mode else "*"*len(buffer)
        draw_text(shown or ("0" if numeric_mode else "____"),FONT_L,WHITE,box.center,True)
        if self.cheat_money_mode:
            draw_text(f"DINHEIRO ATUAL: {SAVE.get('coins',0)}",FONT_S,ORANGE,(W/2,S(270)),True)
        elif self.cheat_value_mode == "wave":
            draw_text(f"PROXIMA RUN COMECARA NA ONDA {SAVE.get('cheat_start_wave',1)}",FONT_S,ORANGE,(W/2,S(270)),True)
        elif self.cheat_value_mode == "evo":
            prof=evolution_profile(self.selected_character); draw_text(f"{self.selected_character}: {prof.get('points',0)} PONTOS LIVRES",FONT_S,CYAN,(W/2,S(270)),True)
        elif self.cheat_message:
            draw_text(self.cheat_message,FONT_S,GREEN if "ACEITO" in self.cheat_message or "ATIVO" in self.cheat_message else RED,(W/2,S(270)),True)
        elif SAVE.get("cheat_all_chars",False):
            draw_text("CODIGO-MESTRE ATIVO",FONT_S,GREEN,(W/2,S(270)),True)

        self.cheat_digit_rects=[]
        bw,bh,gap=S(150),S(78),S(18); total=bw*5+gap*4; x0=W/2-total/2; y0=S(330)
        digits="1234567890"
        for i,digit in enumerate(digits):
            col,row=i%5,i//5; r=pygame.Rect(x0+col*(bw+gap),y0+row*(bh+gap),bw,bh); pygame.draw.rect(SCREEN,PANEL2,r,border_radius=S(15)); draw_text(digit,FONT_M,WHITE,r.center,True); self.cheat_digit_rects.append((r,digit))

        clear=pygame.Rect(W/2-S(360),H-CONTROL_SAFE_Y-S(125),S(300),S(70))
        confirm=pygame.Rect(W/2+S(60),H-CONTROL_SAFE_Y-S(125),S(300),S(70))
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(55),S(210),S(50))
        pygame.draw.rect(SCREEN,RED,clear,border_radius=S(16)); pygame.draw.rect(SCREEN,GREEN,confirm,border_radius=S(16)); pygame.draw.rect(SCREEN,PANEL2,back,border_radius=S(13))
        draw_text("APAGAR",FONT_S,WHITE,clear.center,True); draw_text("DEFINIR" if numeric_mode else "CONFIRMAR",FONT_S,DARK,confirm.center,True); draw_text("VOLTAR",FONT_S,WHITE,back.center,True)
        self.cheat_clear_rect,self.cheat_confirm_rect,self.cheat_back_rect=clear,confirm,back

        self.cheat_money_rect = None
        if money_unlocked:
            r = pygame.Rect(W-CONTROL_SAFE_X-S(300), H-CONTROL_SAFE_Y-S(55), S(300), S(50))
            pygame.draw.rect(SCREEN,ORANGE,r,border_radius=S(13))
            draw_text("CODIGOS" if self.cheat_money_mode else "DINHEIRO",FONT_S,DARK,r.center,True)
            self.cheat_money_rect = r

        self.cheat_extra_rects=[]
        if SAVE.get("cheat_dev",False):
            labels=[
                ("wave","ONDA X",ORANGE),("evo","EVOLUCAO",CYAN),
                ("immortal","IMORTAL: "+("ON" if SAVE.get("cheat_immortal") else "OFF"),GREEN if SAVE.get("cheat_immortal") else PANEL2),
                ("damage","DANO INF: "+("ON" if SAVE.get("cheat_infinite_damage") else "OFF"),GREEN if SAVE.get("cheat_infinite_damage") else PANEL2),
                ("items","ITENS INF: "+("ON" if SAVE.get("cheat_items_infinite") else "OFF"),GREEN if SAVE.get("cheat_items_infinite") else PANEL2),
                ("max_chars","MAX PERSONAGENS",DIVINE_BLUE),
                ("max_perm","MAX PERMANENTES",YELLOW),
                ("passives","DEV PASSIVAS",PINK),
            ]
            cols=4; ew,eh,eg=S(285),S(52),S(14); total=ew*cols+eg*(cols-1); ex=W/2-total/2; ey=S(515)
            for i,(key,label,color) in enumerate(labels):
                col,row=i%cols,i//cols
                rr=pygame.Rect(ex+col*(ew+eg),ey+row*(eh+eg),ew,eh)
                pygame.draw.rect(SCREEN,color,rr,border_radius=S(12))
                draw_text(label,FONT_S,DARK if color in (ORANGE,CYAN,GREEN,DIVINE_BLUE,YELLOW) else WHITE,rr.center,True)
                self.cheat_extra_rects.append((rr,key))

    def cheat_max_all_characters(self):
        """Maximiza a evolucao de todos os personagens que possuem progressao."""
        SAVE["cheat_all_chars"] = True
        for char in CHARACTER_CONFIG:
            if is_beta_character(char):
                continue
            prof = evolution_profile(char)
            for stat in EVOLUTION_STAT_KEYS:
                prof[stat] = MAX_EVOLUTION_STAT
            prof["points"] = 0
            prof["earned"] = max(int(prof.get("earned", 0) or 0), MAX_EVOLUTION_STAT * len(EVOLUTION_STAT_KEYS))
        save_data(SAVE)
        self.cheat_message = "ATIVO: TODOS OS PERSONAGENS MAXIMIZADOS"
        self.unlock_notice = "PERSONAGENS NORMAIS: STATUS MAXIMOS"
        self.unlock_notice_timer = 4.0
        AUDIO.play("unlock", 0.9)

    def cheat_max_permanent_upgrades(self):
        """Coloca todos os upgrades permanentes no limite atual (LV.30)."""
        for key, _name, _desc, _cost in PERMANENT_UPGRADES:
            SAVE[key] = PERMANENT_UPGRADE_CAP
        save_data(SAVE)
        self.cheat_message = f"ATIVO: UPGRADES PERMANENTES LV.{PERMANENT_UPGRADE_CAP}"
        self.unlock_notice = f"TODOS OS UPGRADES PERMANENTES: LV.{PERMANENT_UPGRADE_CAP}"
        self.unlock_notice_timer = 4.0
        AUDIO.play("unlock", 0.9)

    def submit_cheat(self):
        if self.cheat_value_mode in ("wave","evo"):
            try: amount=max(0,min(int(self.cheat_money_buffer or "0"),999999))
            except Exception: amount=0
            if self.cheat_value_mode=="wave":
                SAVE["cheat_start_wave"]=max(1,amount); self.cheat_message=f"ONDA INICIAL: {max(1,amount)}"
            else:
                if is_beta_character(self.selected_character): self.cheat_message="BETA NAO TEM EVOLUCAO"
                else:
                    evolution_profile(self.selected_character)["points"]=amount; self.cheat_message=f"EVOLUCAO {self.selected_character}: {amount}"
            save_data(SAVE); self.cheat_money_buffer=""; return
        if self.cheat_money_mode:
            if not SAVE.get("cheat_money", False):
                self.cheat_message = "PAINEL DEV AINDA NAO ATIVADO"
            else:
                try:
                    amount = int(self.cheat_money_buffer or "0")
                    amount = max(0, min(amount, 999999999))
                    SAVE["coins"] = amount
                    save_data(SAVE)
                    self.cheat_message = f"DINHEIRO DEFINIDO: {amount}"
                    AUDIO.play("unlock", 0.8)
                except Exception:
                    self.cheat_message = "VALOR INVALIDO"
            self.cheat_money_buffer = ""
            return
        if self.cheat_buffer == "6767":
            # Codigo-mestre secreto atual.
            SAVE["cheat_all_chars"] = True
            SAVE["cheat_money"] = True
            SAVE["cheat_dev"] = True
            save_data(SAVE)
            self.cheat_message = "CODIGO-MESTRE ACEITO"
            self.unlock_notice = "PAINEL DEV + PERSONAGENS + DINHEIRO LIBERADOS"
            self.unlock_notice_timer = 4.0
            AUDIO.play("unlock", 1.0)
        else:
            self.cheat_message = "CODIGO INVALIDO"
        self.cheat_buffer = ""

    def draw_backup(self):
        SCREEN.fill(BG)
        draw_text("BACKUP DE PROGRESSO", FONT_L, WHITE, (W/2, S(58)), True)
        draw_text("Guarde o codigo antes de desinstalar ou trocar o APK.", FONT_S, GRAY, (W/2, S(112)), True)

        # Area do codigo gerado.
        code_box = pygame.Rect(SAFE, S(150), W-SAFE*2, S(205))
        pygame.draw.rect(SCREEN, PANEL, code_box, border_radius=S(16))
        pygame.draw.rect(SCREEN, CYAN, code_box, width=max(2,S(3)), border_radius=S(16))
        draw_text("SEU CODIGO DE BACKUP", FONT_S, CYAN, (code_box.x+S(18), code_box.y+S(16)))
        shown = self.backup_code if self.backup_code else "Aperte GERAR CODIGO para criar um backup do progresso atual."
        draw_wrapped_text(shown, FONT_S, WHITE, pygame.Rect(code_box.x+S(18), code_box.y+S(58), code_box.w-S(36), code_box.h-S(72)), 2, False, 5)

        bw, bh, gap = S(330), S(70), S(20)
        total = bw*3 + gap*2
        x0 = W/2-total/2
        generate = pygame.Rect(x0, S(380), bw, bh)
        copy_btn = pygame.Rect(x0+bw+gap, S(380), bw, bh)
        paste_btn = pygame.Rect(x0+(bw+gap)*2, S(380), bw, bh)
        for r,label,color in [(generate,"GERAR CODIGO",GREEN),(copy_btn,"COPIAR",CYAN),(paste_btn,"COLAR",YELLOW)]:
            pygame.draw.rect(SCREEN,color,r,border_radius=S(14))
            draw_text(label,FONT_S,DARK,r.center,True)

        input_box = pygame.Rect(SAFE, S(485), W-SAFE*2, S(150))
        pygame.draw.rect(SCREEN, PANEL2 if self.backup_input_active else PANEL, input_box, border_radius=S(14))
        pygame.draw.rect(SCREEN, YELLOW if self.backup_input_active else GRAY, input_box, width=max(2,S(3)), border_radius=S(14))
        draw_text("CODIGO PARA RESTAURAR - toque aqui para digitar/colar", FONT_S, YELLOW, (input_box.x+S(18), input_box.y+S(14)))
        inp = self.backup_input if self.backup_input else "Cole ou digite o codigo EV11-..."
        # Mostra o final também, porque é onde fica a verificacao do backup.
        if len(inp) > 430:
            inp = "..." + inp[-427:]
        draw_wrapped_text(inp, FONT_S, WHITE if self.backup_input else GRAY, pygame.Rect(input_box.x+S(18),input_box.y+S(54),input_box.w-S(36),input_box.h-S(64)),2,False,3)

        restore = pygame.Rect(W/2-S(360), S(665), S(720), S(78))
        clear = pygame.Rect(W/2-S(360), S(760), S(340), S(66))
        back = pygame.Rect(W/2+S(20), S(760), S(340), S(66))
        pygame.draw.rect(SCREEN, PURPLE, restore, border_radius=S(16))
        pygame.draw.rect(SCREEN, PANEL2, clear, border_radius=S(14))
        pygame.draw.rect(SCREEN, PANEL2, back, border_radius=S(14))
        draw_text("RESTAURAR PROGRESSO", FONT_M, WHITE, restore.center, True)
        draw_text("LIMPAR", FONT_S, WHITE, clear.center, True)
        draw_text("VOLTAR", FONT_S, WHITE, back.center, True)

        if self.backup_message:
            color = GREEN if any(x in self.backup_message for x in ("CRIADO","COPIADO","RESTAURADO","COLADO")) else RED
            draw_text(self.backup_message, FONT_S, color, (W/2, S(865)), True)
        draw_text("Dica: gere o codigo e salve em Notas/WhatsApp/Discord.", FONT_S, GRAY, (W/2, H-CONTROL_SAFE_Y-S(16)), True)

        self.backup_generate_rect = generate
        self.backup_copy_rect = copy_btn
        self.backup_paste_rect = paste_btn
        self.backup_input_rect = input_box
        self.backup_restore_rect = restore
        self.backup_clear_rect = clear
        self.backup_back_rect = back

    def open_backup(self):
        self.backup_code = ""
        self.backup_input = ""
        self.backup_message = ""
        self.backup_input_active = False
        self.state = "backup"

    def backup_start_input(self):
        self.backup_input_active = True
        try:
            pygame.key.start_text_input()
        except Exception:
            pass

    def backup_stop_input(self):
        self.backup_input_active = False
        try:
            pygame.key.stop_text_input()
        except Exception:
            pass

    def generate_backup(self):
        try:
            self.backup_code = make_backup_code(SAVE)
            self.backup_message = "BACKUP CRIADO! GUARDE O CODIGO."
            AUDIO.play("unlock", 0.55)
        except Exception:
            self.backup_message = "NAO FOI POSSIVEL GERAR O BACKUP"

    def copy_backup(self):
        if not self.backup_code:
            self.generate_backup()
        if self.backup_code and clipboard_put_text(self.backup_code):
            self.backup_message = "CODIGO COPIADO PARA O ANDROID!"
        else:
            self.backup_message = "NAO COPIOU - VERIFIQUE SE A BUILD INCLUI PYJNIUS"

    def paste_backup(self):
        text = clipboard_get_text()
        if text:
            self.backup_input = text[:12000]
            self.backup_message = "CODIGO COLADO!"
        else:
            self.backup_message = "COLAR INDISPONIVEL - TOQUE NA CAIXA E COLE PELO TECLADO"
            self.backup_start_input()

    def restore_backup(self):
        global SAVE
        try:
            restored = restore_backup_code(self.backup_input)
            SAVE.clear()
            SAVE.update(restored)
            for _perm_key, _perm_name, _perm_desc, _perm_base in PERMANENT_UPGRADES:
                SAVE[_perm_key]=max(0,min(PERMANENT_UPGRADE_CAP,int(SAVE.get(_perm_key,0) or 0)))
            save_data(SAVE)
            AUDIO.set_sfx_volume(int(SAVE.get("sfx_volume", 70 if SAVE.get("sfx_on", True) else 0)))
            AUDIO.set_music_volume(int(SAVE.get("music_volume", 30 if SAVE.get("music_on", True) else 0)))
            self.buttons = self.make_buttons()
            self.backup_message = "PROGRESSO RESTAURADO!"
            self.backup_code = make_backup_code(SAVE)
            self.backup_stop_input()
            AUDIO.play("unlock", 0.8)
        except ValueError as exc:
            self.backup_message = str(exc)
        except Exception:
            self.backup_message = "FALHA AO RESTAURAR"

    def draw_vinicius_mega_choice(self):
        SCREEN.fill(BG)
        draw_text("20 SUCATAS INIMIGAS",FONT_L,RED,(W/2,S(72)),True)
        draw_text("ESCOLHA UMA MEGA TORRE",FONT_M,WHITE,(W/2,S(126)),True)
        cards=[("hospital","HOSPITAL-AUTOMATICO","Cura SOMENTE as torretas em qualquer ponto da arena.",CYAN),("anti_titan","CANHAO ANTI-TITA","A cada 5s arranca 50% da vida do inimigo mais forte e causa dano em area.",ORANGE),("ballistic","BALISTICA AUTOMATICA","Dispara mini bolinhas rapidamente no inimigo mais proximo; alcance da arena inteira.",YELLOW)]
        gap=S(22); cw=int((W-CONTROL_SAFE_X*2-gap*2)/3); ch=S(430); y=S(185); self.vinicius_mega_choice_rects=[]
        for i,(key,name,desc,color) in enumerate(cards):
            r=pygame.Rect(CONTROL_SAFE_X+i*(cw+gap),y,cw,ch); pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(22)); pygame.draw.rect(SCREEN,color,r,max(2,S(5)),border_radius=S(22))
            draw_text("MEGA TORRE",FONT_S,color,(r.centerx,r.y+S(38)),True)
            draw_wrapped_text(name,FONT_M,WHITE,pygame.Rect(r.x+S(20),r.y+S(78),r.w-S(40),S(95)),2,True,2)
            draw_wrapped_text(desc,FONT_S,GRAY,pygame.Rect(r.x+S(24),r.y+S(195),r.w-S(48),S(130)),3,True,4)
            b=pygame.Rect(r.x+S(30),r.bottom-S(85),r.w-S(60),S(60)); pygame.draw.rect(SCREEN,color,b,border_radius=S(14)); draw_text("CONSTRUIR",FONT_S,DARK,b.center,True); self.vinicius_mega_choice_rects.append((b,key))

    def start_lira_domain_choice(self):
        if self.player.character!=LIRA_KEY or not self.domain_active: return
        for e in self.enemies: e.lira_domain_stats=set()
        self.lira_domain_selected=[]
        self.state="lira_domain_choice"

    def choose_lira_domain_stat(self,key):
        if key in self.lira_domain_selected:
            self.lira_domain_selected.remove(key); AUDIO.play("click",0.45); return
        need=3 if getattr(self.player,"lira_nothing_published",False) else 2
        if len(self.lira_domain_selected)>=need: return
        self.lira_domain_selected.append(key); AUDIO.play("click",0.55)
        if len(self.lira_domain_selected)>=need: self.finalize_lira_domain_choice()

    def finalize_lira_domain_choice(self):
        need=3 if getattr(self.player,"lira_nothing_published",False) else 2
        if self.player.character!=LIRA_KEY or not self.domain_active or len(self.lira_domain_selected)!=need: return
        chosen=set(self.lira_domain_selected); p=self.player; p.lira_domain_buffs=set(chosen)
        if "life" in chosen and p.lira_life_bonus<=0:
            p.lira_life_bonus=p.max_hp*0.50; p.max_hp+=p.lira_life_bonus; p.hp=min(p.max_hp,p.hp+p.lira_life_bonus)
        targets=[e for e in list(self.enemies) if not e.dead and self.is_in_domain(e.pos)]
        for e in targets:
            e.lira_domain_stats=set(chosen)
            if "life" in chosen and not e.dead:
                e.hp-=e.max_hp*0.50; self.damage_texts.append(DamageText("VIDA -50%",pygame.Vector2(e.pos),RED,0.8))
                if e.hp<=0: e.hp=0; e.die(self)
        labels={"strength":"FORCA -70%","life":"VIDA -50%","resistance":"RESISTENCIA -100%","speed":"VELOCIDADE -50%","intelligence":"INTELIGENCIA -100%"}
        self.damage_texts.append(DamageText(" + ".join(labels[x] for x in self.lira_domain_selected),pygame.Vector2(p.pos),LIRA_ACCENT,1.2))
        self.state="playing"; self.shake=max(self.shake,S(12)); self.flash_screen=max(self.flash_screen,0.08)
        for e in self.enemies:
            if isinstance(e,Boss) and not e.dead and e.domain_active and self.domains_overlap(e): self.start_domain_clash(e); break

    def draw_lira_domain_choice(self):
        SCREEN.fill(BG)
        draw_text("EXPANSAO DE DOMINIO",FONT_S,LIRA_ACCENT,(W/2,S(45)),True)
        draw_text("&#$*%@!??",FONT_XL,WHITE,(W/2,S(100)),True)
        draw_text("ESCOLHA 3 CENSURAS" if getattr(self.player,"lira_nothing_published",False) else "ESCOLHA 2 CENSURAS",FONT_M,LIRA_ACCENT,(W/2,S(158)),True)
        draw_text("QUEM ESTIVER DENTRO NA SEGUNDA ESCOLHA FICA MARCADO ATE O FIM",FONT_S,GRAY,(W/2,S(200)),True)
        cards=[("strength","FORCA","-70% dano causado","LIRA: +70% dano",RED),("life","VIDA","-50% do HP total","LIRA: +50% HP temporario",GREEN),("resistance","RESISTENCIA","-100%: dano bruto","LIRA: -50% dano recebido",DIVINE_BLUE),("speed","VELOCIDADE","-50% velocidade","LIRA: +50% velocidade",YELLOW),("intelligence","INTELIGENCIA","-100%: perde o alvo e foge","LIRA: menos cooldown + mais alcance",PURPLE)]
        gap=S(12); margin=CONTROL_SAFE_X; cw=int((W-margin*2-gap*4)/5); ch=S(465); y=S(245); self.lira_domain_choice_rects=[]
        for i,(key,name,enemy_desc,lira_desc,color) in enumerate(cards):
            r=pygame.Rect(margin+i*(cw+gap),y,cw,ch); selected=key in self.lira_domain_selected
            pygame.draw.rect(SCREEN,(62,64,78) if selected else (42,44,56),r,border_radius=S(18)); pygame.draw.rect(SCREEN,color if selected else GRAY,r,max(2,S(5 if selected else 3)),border_radius=S(18))
            draw_text(name,FONT_M,color,(r.centerx,r.y+S(46)),True)
            draw_wrapped_text(enemy_desc,FONT_S,WHITE,pygame.Rect(r.x+S(14),r.y+S(105),r.w-S(28),S(100)),3,True,3)
            draw_wrapped_text(lira_desc,FONT_S,LIRA_ACCENT,pygame.Rect(r.x+S(14),r.y+S(245),r.w-S(28),S(110)),3,True,3)
            draw_text("ESCOLHIDO" if selected else "ESCOLHER",FONT_S,WHITE,(r.centerx,r.bottom-S(48)),True)
            self.lira_domain_choice_rects.append((r,key))
        draw_text(f"{len(self.lira_domain_selected)}/2",FONT_M,WHITE,(W/2,H-CONTROL_SAFE_Y-S(38)),True)

    def draw_glonk_death(self):
        SCREEN.fill(BG)
        draw_text("Parabéns! Glonk cumpriu seu papel", FONT_L, WHITE, (W/2, H*0.43), True)
        menu = pygame.Rect(W/2-S(260), H*0.60, S(520), S(90))
        pygame.draw.rect(SCREEN, PANEL2, menu, border_radius=S(22))
        draw_text("VOLTAR AO MENU", FONT_M, WHITE, menu.center, True)
        self.glonk_menu_rect = menu

    def draw(self):
        if self.state == "menu":
            self.draw_menu()
        elif self.state == "mode_select":
            self.draw_mode_select()
        elif self.state == "character_select":
            self.draw_character_select()
        elif self.state == "difficulty_select":
            self.draw_difficulty_select()
        elif self.state == "curse_choice":
            self.draw_curse_choice()
        elif self.state == "mode_complete":
            self.draw_mode_complete()
        elif self.state == "shop":
            self.draw_shop()
        elif self.state == "upgrade_catalog":
            self.draw_upgrade_catalog()
        elif self.state == "passive_catalog":
            self.draw_passive_catalog()
        elif self.state == "passive_roll":
            self.draw_passive_roll()
        elif self.state == "passive_auto_config":
            self.draw_passive_auto_config()
        elif self.state == "passive_dev":
            self.draw_passive_dev()
        elif self.state == "bestiary":
            self.draw_bestiary()
        elif self.state == "forge":
            self.draw_forge()
        elif self.state == "items":
            self.draw_items()
        elif self.state == "weapons":
            self.draw_weapons()
        elif self.state == "control_editor":
            self.draw_control_editor()
        elif self.state == "run_upgrades":
            self.draw_run_upgrades()
        elif self.state == "whats_new":
            self.draw_whats_new()
        elif self.state == "settings":
            self.draw_settings()
        elif self.state == "achievements":
            self.draw_achievements()
        elif self.state == "missions":
            self.draw_missions()
        elif self.state == "cheats":
            self.draw_cheats()
        elif self.state == "backup":
            self.draw_backup()
        elif self.state == "vinicius_mega":
            self.draw_vinicius_mega_choice()
        elif self.state == "lira_domain_choice":
            self.draw_lira_domain_choice()
        elif self.state == "playing":
            self.draw_playing()
        elif self.state == "paused":
            self.draw_paused()
        elif self.state == "glonk_death":
            self.draw_glonk_death()
        elif self.state == "upgrade":
            self.draw_upgrade()
        elif self.state == "death":
            self.draw_death()

    def draw_mode_select(self):
        SCREEN.fill(BG)
        draw_text("MODOS DE JOGO",FONT_L,WHITE,(W/2,S(55)),True)
        draw_text("CADA MODO MUDA AS REGRAS DA PARTIDA",FONT_S,CYAN,(W/2,S(105)),True)
        self.game_mode_rects=[]
        margin=CONTROL_SAFE_X; gap=S(18); cols=3; card_w=int((W-margin*2-gap*(cols-1))/cols); card_h=S(205); y0=S(145)
        for i,key in enumerate(GAME_MODE_ORDER):
            row=i//3; col=i%3; r=pygame.Rect(margin+col*(card_w+gap),y0+row*(card_h+gap),card_w,card_h)
            cfg=GAME_MODES[key]; unlocked=self.mode_unlocked(key)
            color=cfg["color"] if unlocked else GRAY
            pygame.draw.rect(SCREEN,PANEL if unlocked else (24,24,30),r,border_radius=S(18)); pygame.draw.rect(SCREEN,color,r,max(2,S(4)),border_radius=S(18))
            label=cfg["name"] if unlocked else "[LOCK] "+cfg["name"]
            draw_text(label,FONT_M,color,(r.centerx,r.y+S(34)),True)
            desc=cfg["desc"] if unlocked else self.mode_lock_text(key)
            draw_wrapped_text(desc,FONT_S,WHITE if unlocked else GRAY,pygame.Rect(r.x+S(18),r.y+S(72),r.w-S(36),S(88)),3,True,3)
            if unlocked:
                rec=self.mode_record(key); metric="KOs" if key=="arena_survival" else "WAVE"
                draw_text(f"RECORDE {metric}: {rec}",FONT_S,GRAY,(r.centerx,r.bottom-S(26)),True)
            self.game_mode_rects.append((r,key,unlocked))
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(58),S(210),S(58)); pygame.draw.rect(SCREEN,PANEL2,back,border_radius=S(14)); draw_text("< MENU",FONT_S,WHITE,back.center,True); self.mode_select_back_rect=back

    def draw_curse_choice(self):
        SCREEN.fill((18,10,30)); draw_text("ESCOLHA UMA MALDICAO",FONT_L,PURPLE,(W/2,S(100)),True); draw_text("VOCE E OBRIGADO A CARREGAR UMA DELAS ATE O FIM",FONT_S,WHITE,(W/2,S(150)),True)
        self.curse_choice_rects=[]; cw=S(650); ch=S(280); gap=S(60); total=cw*2+gap; x0=(W-total)/2; y=S(260)
        for i,c in enumerate(self.curse_choice_cards):
            key,name,desc=c; r=pygame.Rect(x0+i*(cw+gap),y,cw,ch); pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(24)); pygame.draw.rect(SCREEN,PURPLE,r,max(2,S(6)),border_radius=S(24)); draw_text(name,FONT_M,PURPLE,(r.centerx,r.y+S(65)),True); draw_wrapped_text(desc,FONT_M,WHITE,pygame.Rect(r.x+S(30),r.y+S(125),r.w-S(60),S(100)),4,True,3); self.curse_choice_rects.append((r,key))

    def draw_mode_complete(self):
        SCREEN.fill(BG); draw_text(self.mode_complete_title or "MODO COMPLETO",FONT_XL,YELLOW,(W/2,H*0.30),True); draw_text(self.mode_complete_subtitle,FONT_M,WHITE,(W/2,H*0.43),True);
        r=pygame.Rect(W/2-S(250),H*0.58,S(500),S(90)); pygame.draw.rect(SCREEN,GREEN,r,border_radius=S(20)); draw_text("VOLTAR AO MENU",FONT_M,DARK,r.center,True); self.mode_complete_menu_rect=r

    def draw_difficulty_select(self):
        SCREEN.fill(BG)
        name = self.pending_character or self.selected_character
        draw_text("ESCOLHA A DIFICULDADE", FONT_L, WHITE, (W/2, S(70)), True)
        gm=GAME_MODES.get(self.game_mode,GAME_MODES["normal"])["name"]
        draw_text(f"PERSONAGEM: {name.upper()} | MODO: {gm}", FONT_S, GRAY, (W/2, S(125)), True)
        self.difficulty_rects = []
        gap = S(18)
        margin = CONTROL_SAFE_X
        card_w = int((W - margin*2 - gap*4) / 5)
        card_h = min(S(570), H-S(285))
        y = S(185)
        for i,key in enumerate(DIFFICULTY_ORDER):
            cfg=DIFFICULTIES[key]
            r=pygame.Rect(margin+i*(card_w+gap),y,card_w,card_h)
            pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(22))
            pygame.draw.rect(SCREEN,cfg["color"],r,max(2,S(5)),border_radius=S(22))
            draw_text(cfg["name"],FONT_M,cfg["color"],(r.centerx,r.y+S(48)),True)
            draw_wrapped_text(cfg["desc"],FONT_S,WHITE,pygame.Rect(r.x+S(18),r.y+S(95),r.w-S(36),S(115)),3,True,4)
            stats=[
                f"HP x{cfg['hp']:.2f}", f"FORCA x{cfg['force']:.2f}", f"DANO x{cfg['damage']:.2f}", f"VEL x{cfg['speed']:.2f}",
                f"INTELIGENCIA x{cfg['ai']:.2f}", f"QUANTIDADE x{cfg['count']:.2f}", f"RECOMPENSAS {int(cfg['reward']*100)}%"
            ]
            yy=r.y+S(225)
            for line in stats:
                draw_text(line,FONT_S,GRAY,(r.centerx,yy),True); yy+=S(34)
            if key=="impossible":
                warn=pygame.Rect(r.x+S(12),r.bottom-S(125),r.w-S(24),S(64))
                pygame.draw.rect(SCREEN,(70,20,28),warn,border_radius=S(12))
                draw_wrapped_text("ACERTO = -10% HP MAX + ESTAMINA",FONT_S,RED,warn,2,True,2)
            draw_text("TOQUE PARA JOGAR",FONT_S,cfg["color"],(r.centerx,r.bottom-S(30)),True)
            self.difficulty_rects.append((r,key))
        back=pygame.Rect(CONTROL_SAFE_X,H-CONTROL_SAFE_Y-S(58),S(230),S(58))
        pygame.draw.rect(SCREEN,PANEL2,back,border_radius=S(14)); draw_text("< PERSONAGEM",FONT_S,WHITE,back.center,True)
        self.difficulty_back_rect=back

    def click_ui(self, pos):
        if self.state == "menu":
            if hasattr(self, "menu_settings_rect") and self.menu_settings_rect.collidepoint(pos):
                AUDIO.play("click",0.65); self.open_settings("menu")
            elif self.menu_start_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.open_mode_select()
            elif self.menu_afk_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.open_character_select("afk")
            elif self.menu_shop_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.state = "shop"
            elif self.menu_upgrades_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.catalog_page = 0; self.upgrade_catalog_tab="found"; self.state = "upgrade_catalog"
            elif self.menu_bestiary_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.bestiary_page = 0; self.state = "bestiary"
            elif hasattr(self,"menu_passives_rect") and self.menu_passives_rect.collidepoint(pos):
                AUDIO.play("click",0.75); self.open_passive_roll(self.selected_character,"menu")
            elif self.menu_controls_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.state = "control_editor"
            elif self.menu_news_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.whats_new_version="V15"; self.whats_new_scroll=0.0; self.state = "whats_new"
            elif self.menu_achievements_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.achievement_page = 0; self.state = "achievements"
            elif self.menu_missions_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "missions"
            elif self.menu_cheats_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.cheat_buffer = ""; self.cheat_money_buffer = ""; self.cheat_money_mode = False; self.cheat_value_mode=None; self.cheat_message = ""; self.state = "cheats"
            elif hasattr(self, "menu_forge_rect") and self.menu_forge_rect.collidepoint(pos):
                AUDIO.play("click",0.65); self.forge_page=0; self.forge_character_index=0; self.state="forge"
            elif hasattr(self, "menu_items_rect") and self.menu_items_rect.collidepoint(pos):
                AUDIO.play("click",0.65); self.items_page=0; self.items_tab="materials"; self.state="items"
            elif hasattr(self, "menu_weapons_rect") and self.menu_weapons_rect.collidepoint(pos):
                AUDIO.play("click",0.65); self.weapons_page=0; self.weapons_character_index=0; self.state="weapons"
            elif hasattr(self, "menu_backup_rect") and self.menu_backup_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.open_backup()

        elif self.state == "mode_select":
            if self.mode_select_back_rect.collidepoint(pos): self.state="menu"; AUDIO.play("click",0.55)
            else:
                for r,key,unlocked in self.game_mode_rects:
                    if r.collidepoint(pos):
                        if not unlocked:
                            self.unlock_notice=self.mode_lock_text(key); self.unlock_notice_timer=2.0; AUDIO.play("hurt",0.4,100); break
                        self.game_mode=key; self.pending_game_mode=key; AUDIO.play("click",0.75)
                        if key=="rogue":
                            candidates=[c for c in CHARACTER_ORDER if self.character_unlocked(c) and c!="Glonk"]; chosen=random.choice(candidates) if candidates else "Ycaro"; self.selected_character=chosen; self.open_difficulty_select(chosen)
                        else: self.open_character_select("arena")
                        break

        elif self.state == "character_select":
            if self.character_back_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "mode_select" if self.selection_target=="arena" else "menu"
            elif self.character_main_tab_rect.collidepoint(pos):
                AUDIO.play("click",0.55); self.character_tab = "characters"; self.character_carousel_index = 0
            elif self.character_beta_tab_rect.collidepoint(pos):
                AUDIO.play("click",0.55); self.character_tab = "beta"; self.character_carousel_index = 0
            elif self.character_tab in ("characters", "beta"):
                if self.character_prev_rect.collidepoint(pos):
                    self.character_carousel_index = (self.character_carousel_index-1)%len(self.current_character_order()); AUDIO.play("click",0.45)
                elif self.character_next_rect.collidepoint(pos):
                    self.character_carousel_index = (self.character_carousel_index+1)%len(self.current_character_order()); AUDIO.play("click",0.45)
                else:
                    if hasattr(self,"character_passive_rect") and self.character_passive_rect.collidepoint(pos):
                        name=self.selected_carousel_character()
                        if not is_beta_character(name) and self.character_unlocked(name):
                            self.open_passive_roll(name,"character_select"); AUDIO.play("click",0.7)
                        return
                    spent = False
                    for r, stat, can in self.character_stat_plus_rects:
                        if r.collidepoint(pos):
                            if can: self.spend_evolution_point(stat)
                            spent = True
                            break
                    if not spent:
                        changed = False
                        for item in self.character_rects:
                            r,name,unlocked,idx = item
                            if r.collidepoint(pos) and idx != self.character_carousel_index:
                                self.character_carousel_index = idx
                                AUDIO.play("click",0.45)
                                changed = True
                                break
                        if not changed and self.character_play_rect.collidepoint(pos):
                            name = self.selected_carousel_character()
                            if self.character_unlocked(name):
                                AUDIO.play("click", 0.75)
                                self.selected_character = name
                                if self.selection_target == "afk":
                                    self.start_afk(name)
                                else:
                                    self.open_difficulty_select(name)

        elif self.state == "difficulty_select":
            if hasattr(self,"difficulty_back_rect") and self.difficulty_back_rect.collidepoint(pos):
                AUDIO.play("click",0.55); self.state="character_select"
            else:
                for r,key in getattr(self,"difficulty_rects",[]):
                    if r.collidepoint(pos):
                        chosen=self.pending_character or self.selected_character
                        self.difficulty=key
                        AUDIO.play("click",0.75)
                        self.reset_run(chosen,key)
                        break

        elif self.state == "curse_choice":
            for r,key in self.curse_choice_rects:
                if r.collidepoint(pos): self.choose_infinite_curse(key); break

        elif self.state == "mode_complete":
            if hasattr(self,"mode_complete_menu_rect") and self.mode_complete_menu_rect.collidepoint(pos): self.state="menu"; AUDIO.play("click",0.6)

        elif self.state == "paused":
            if hasattr(self, "pause_settings_rect") and self.pause_settings_rect.collidepoint(pos):
                AUDIO.play("click",0.65); self.open_settings("paused")
            elif self.pause_resume_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "playing"
            elif self.pause_upgrades_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.run_upgrade_page = 0; self.state = "run_upgrades"
            elif self.pause_menu_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.leave_run_to_menu()

        elif self.state == "upgrade_catalog":
            tab=getattr(self,"upgrade_catalog_tab","found")
            count=len(UPGRADE_SYNERGIES) if tab=="synergies" else len(self.upgrade_catalog_entries())
            pages=max(1,math.ceil(max(1,count)/6))
            if self.catalog_back_rect.collidepoint(pos):
                AUDIO.play("click",0.65); self.state="menu"
            elif any(r.collidepoint(pos) for r,_ in getattr(self,"upgrade_catalog_tab_rects",[])):
                self.upgrade_catalog_tab=next(key for r,key in self.upgrade_catalog_tab_rects if r.collidepoint(pos)); self.catalog_page=0; AUDIO.play("click",0.55)
            elif self.catalog_prev_rect.collidepoint(pos):
                AUDIO.play("click",0.55); self.catalog_page=(self.catalog_page-1)%pages
            elif self.catalog_next_rect.collidepoint(pos):
                AUDIO.play("click",0.55); self.catalog_page=(self.catalog_page+1)%pages

        elif self.state == "passive_catalog":
            discovered=set(SAVE.get("passive_discovered",[]))
            entries=[x for x in PASSIVES if x["key"] in discovered] if self.passive_catalog_tab=="known" else list(PASSIVES)
            pages=max(1,math.ceil(max(1,len(entries))/6))
            if self.passive_catalog_back_rect.collidepoint(pos): self.state=getattr(self,"passive_catalog_return_state","menu"); AUDIO.play("click",.5)
            elif self.passive_catalog_known_rect.collidepoint(pos): self.passive_catalog_tab="known"; self.passive_catalog_page=0; AUDIO.play("click",.5)
            elif self.passive_catalog_all_rect.collidepoint(pos): self.passive_catalog_tab="all"; self.passive_catalog_page=0; AUDIO.play("click",.5)
            elif self.passive_catalog_prev_rect.collidepoint(pos): self.passive_catalog_page=(self.passive_catalog_page-1)%pages
            elif self.passive_catalog_next_rect.collidepoint(pos): self.passive_catalog_page=(self.passive_catalog_page+1)%pages
            elif self.passive_catalog_roll_rect.collidepoint(pos):
                if getattr(self,"passive_catalog_return_state","menu")=="passive_roll": self.state="passive_roll"
                else: self.open_passive_roll(self.selected_character,"menu")
                AUDIO.play("click",.6)

        elif self.state == "passive_roll":
            if self.passive_auto_warning:
                if self.passive_warning_yes_rect.collidepoint(pos):
                    self.passive_auto_warning=False; self.start_passive_auto(ignore_protection=True)
                elif self.passive_warning_no_rect.collidepoint(pos):
                    self.passive_auto_warning=False; self.passive_roll_message="REAL PARCA. SLOT PROTEGIDO."
            elif self.passive_roll_back_rect.collidepoint(pos) and not self.passive_roll_spinning:
                self.passive_auto_mode=False; self.state=self.passive_roll_return_state; AUDIO.play("click",.5)
            elif self.passive_roll_char_prev_rect.collidepoint(pos): self.cycle_passive_roll_character(-1); AUDIO.play("click",.4)
            elif self.passive_roll_char_next_rect.collidepoint(pos): self.cycle_passive_roll_character(1); AUDIO.play("click",.4)
            elif self.passive_roll_button.collidepoint(pos) and not self.passive_roll_spinning: self.roll_passive()
            elif self.passive_auto_button.collidepoint(pos): self.start_passive_auto()
            elif self.passive_auto_config_button.collidepoint(pos) and not self.passive_roll_spinning: self.open_passive_auto_config()
            elif hasattr(self,"passive_roll_catalog_rect") and self.passive_roll_catalog_rect.collidepoint(pos) and not self.passive_roll_spinning:
                self.passive_catalog_page=0; self.passive_catalog_tab="known"; self.passive_catalog_return_state="passive_roll"; self.state="passive_catalog"; AUDIO.play("click",.6)
            elif any(r.collidepoint(pos) for r in self.passive_roll_slot_rects) and not self.passive_roll_spinning:
                for i,r in enumerate(self.passive_roll_slot_rects):
                    if r.collidepoint(pos): self.passive_roll_slot=i; self.passive_auto_mode=False; AUDIO.play("click",.4); break

        elif self.state == "passive_auto_config":
            entries=[x for x in PASSIVES if x.get("rollable",True)]; pages=max(1,math.ceil(len(entries)/8))
            if self.passive_auto_config_back_rect.collidepoint(pos): self.state="passive_roll"; save_data(SAVE)
            elif self.passive_auto_config_prev_rect.collidepoint(pos): self.passive_auto_config_page=(self.passive_auto_config_page-1)%pages
            elif self.passive_auto_config_next_rect.collidepoint(pos): self.passive_auto_config_page=(self.passive_auto_config_page+1)%pages
            elif self.passive_auto_config_clear_rect.collidepoint(pos): SAVE["passive_auto_stop_rarities"]=[]; SAVE["passive_auto_stop_keys"]=[]; save_data(SAVE)
            elif any(r.collidepoint(pos) for r,_ in self.passive_auto_rarity_rects):
                key=next(k for r,k in self.passive_auto_rarity_rects if r.collidepoint(pos)); vals=list(SAVE.get("passive_auto_stop_rarities",[])); vals.remove(key) if key in vals else vals.append(key); SAVE["passive_auto_stop_rarities"]=vals; save_data(SAVE)
            elif any(r.collidepoint(pos) for r,_ in self.passive_auto_key_rects):
                key=next(k for r,k in self.passive_auto_key_rects if r.collidepoint(pos)); vals=list(SAVE.get("passive_auto_stop_keys",[])); vals.remove(key) if key in vals else vals.append(key); SAVE["passive_auto_stop_keys"]=vals; save_data(SAVE)

        elif self.state == "passive_dev":
            pages=max(1,math.ceil(len(PASSIVES)/12))
            if self.passive_dev_back_rect.collidepoint(pos): self.state="cheats"
            elif self.passive_dev_char_prev_rect.collidepoint(pos): self.cycle_passive_dev_character(-1)
            elif self.passive_dev_char_next_rect.collidepoint(pos): self.cycle_passive_dev_character(1)
            elif self.passive_dev_prev_rect.collidepoint(pos): self.passive_dev_page=(self.passive_dev_page-1)%pages
            elif self.passive_dev_next_rect.collidepoint(pos): self.passive_dev_page=(self.passive_dev_page+1)%pages
            elif self.passive_dev_clear_rect.collidepoint(pos):
                pp=passive_character_profile(self.passive_dev_character); pp["equipped"][self.passive_dev_slot]=None; save_data(SAVE)
            elif any(r.collidepoint(pos) for r in self.passive_dev_slot_rects):
                for i,r in enumerate(self.passive_dev_slot_rects):
                    if r.collidepoint(pos): self.passive_dev_slot=i; break
            elif any(r.collidepoint(pos) for r,_ in self.passive_dev_key_rects):
                key=next(k for r,k in self.passive_dev_key_rects if r.collidepoint(pos)); passive_set_slot(self.passive_dev_character,key,self.passive_dev_slot); save_data(SAVE); AUDIO.play("unlock",.6)

        elif self.state == "forge":
            char=FORGE_CHARACTER_ORDER[self.forge_character_index % len(FORGE_CHARACTER_ORDER)]
            pages=max(1,math.ceil(len(self._forge_character_weapons(char))/3))
            if self.forge_back_rect.collidepoint(pos): self.state="menu"
            elif self.forge_char_prev_rect.collidepoint(pos): self.forge_character_index=(self.forge_character_index-1)%len(FORGE_CHARACTER_ORDER); self.forge_page=0
            elif self.forge_char_next_rect.collidepoint(pos): self.forge_character_index=(self.forge_character_index+1)%len(FORGE_CHARACTER_ORDER); self.forge_page=0
            elif self.forge_prev_rect.collidepoint(pos): self.forge_page=(self.forge_page-1)%pages
            elif self.forge_next_rect.collidepoint(pos): self.forge_page=(self.forge_page+1)%pages
            else:
                for r,key,owned in self.forge_recipe_rects:
                    if r.collidepoint(pos):
                        self.equip_weapon(key) if owned else self.craft_weapon(key); break
        elif self.state == "items":
            if self.items_back_rect.collidepoint(pos): self.state="menu"
            elif self.items_material_tab_rect.collidepoint(pos): self.items_tab="materials"; self.items_page=0
            elif self.items_sin_tab_rect.collidepoint(pos): self.items_tab="sins"; self.items_page=0
            else:
                keys=list(SIN_FRAGMENTS.keys()) if self.items_tab=="sins" else [k for k in FORGE_MATERIALS if k not in SIN_FRAGMENTS]
                per=4 if self.items_tab=="sins" else 5
                pages=max(1,math.ceil(len(keys)/per))
                if pages>1 and self.items_prev_rect.collidepoint(pos): self.items_page=(self.items_page-1)%pages
                elif pages>1 and self.items_next_rect.collidepoint(pos): self.items_page=(self.items_page+1)%pages
        elif self.state == "weapons":
            char=FORGE_CHARACTER_ORDER[self.weapons_character_index % len(FORGE_CHARACTER_ORDER)]
            pages=max(1,math.ceil(len(self._forge_character_weapons(char))/3))
            if self.weapons_back_rect.collidepoint(pos): self.state="menu"
            elif self.weapons_char_prev_rect.collidepoint(pos): self.weapons_character_index=(self.weapons_character_index-1)%len(FORGE_CHARACTER_ORDER); self.weapons_page=0
            elif self.weapons_char_next_rect.collidepoint(pos): self.weapons_character_index=(self.weapons_character_index+1)%len(FORGE_CHARACTER_ORDER); self.weapons_page=0
            elif self.weapons_prev_rect.collidepoint(pos): self.weapons_page=(self.weapons_page-1)%pages
            elif self.weapons_next_rect.collidepoint(pos): self.weapons_page=(self.weapons_page+1)%pages
            else:
                for r,key in self.weapon_equip_rects:
                    if r.collidepoint(pos): self.equip_weapon(key); break

        elif self.state == "bestiary":
            visible_entries=[item for item in BESTIARY_ENTRIES if not item.get("hidden_key") or SAVE.get(item.get("hidden_key"),False)]
            pages = max(1, math.ceil(len(visible_entries)/6))
            if self.bestiary_back_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "menu"
            elif any(r.collidepoint(pos) for r,_ in getattr(self,"bestiary_train_rects",[])):
                item=next(item for r,item in self.bestiary_train_rects if r.collidepoint(pos)); AUDIO.play("click",0.7); self.start_bestiary_training(item)
            elif self.bestiary_prev_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.bestiary_page = (self.bestiary_page - 1) % pages
            elif self.bestiary_next_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.bestiary_page = (self.bestiary_page + 1) % pages

        elif self.state == "run_upgrades":
            card_by_key = {card[3]: (source, card) for source, card in self.all_upgrade_entries()}
            count = sum(1 for key in self.owned_upgrade_counts if key in card_by_key)
            pages = max(1, math.ceil(max(1, count)/8))
            if self.run_upgrades_back_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "paused"
            elif self.run_upgrades_prev_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.run_upgrade_page = (self.run_upgrade_page - 1) % pages
            elif self.run_upgrades_next_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.run_upgrade_page = (self.run_upgrade_page + 1) % pages

        elif self.state == "glonk_death":
            if self.glonk_menu_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "menu"

        elif self.state == "shop":
            pages = max(1, math.ceil(len(PERMANENT_UPGRADES)/6))
            if self.shop_back_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "menu"
            elif self.shop_prev_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.shop_page = (self.shop_page-1) % pages
            elif self.shop_next_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.shop_page = (self.shop_page+1) % pages
            else:
                for r, key, cost, can_buy in self.shop_rects:
                    if r.collidepoint(pos) and can_buy and SAVE["coins"] >= cost:
                        AUDIO.play("upgrade", 0.75)
                        SAVE["coins"] -= cost
                        SAVE[key] = min(PERMANENT_UPGRADE_CAP, SAVE.get(key, 0) + 1)
                        save_data(SAVE)
                        break

        elif self.state == "whats_new":
            self.whats_new_down(pos)
            self.whats_new_up(pos)

        elif self.state == "achievements":
            pages = max(1, math.ceil(len(ACHIEVEMENTS)/6))
            if self.achievements_back_rect.collidepoint(pos): self.state = "menu"
            elif self.achievements_prev_rect.collidepoint(pos): self.achievement_page = (self.achievement_page-1) % pages
            elif self.achievements_next_rect.collidepoint(pos): self.achievement_page = (self.achievement_page+1) % pages

        elif self.state == "missions":
            chars = list(CHARACTER_MISSIONS.keys())
            if self.missions_back_rect.collidepoint(pos): self.state = "menu"
            elif self.missions_prev_rect.collidepoint(pos): self.mission_character_index = (self.mission_character_index-1) % len(chars)
            elif self.missions_next_rect.collidepoint(pos): self.mission_character_index = (self.mission_character_index+1) % len(chars)

        elif self.state == "cheats":
            if self.cheat_back_rect.collidepoint(pos): self.state = "menu"
            elif self.cheat_money_rect is not None and self.cheat_money_rect.collidepoint(pos):
                self.cheat_money_mode = not self.cheat_money_mode; self.cheat_value_mode=None
                self.cheat_buffer = ""; self.cheat_money_buffer = ""; self.cheat_message = ""
            elif any(r.collidepoint(pos) for r,_ in self.cheat_extra_rects):
                key=next(k for r,k in self.cheat_extra_rects if r.collidepoint(pos))
                if key in ("wave","evo"):
                    self.cheat_value_mode=key; self.cheat_money_mode=False; self.cheat_money_buffer=""; self.cheat_buffer=""
                elif key=="immortal": SAVE["cheat_immortal"]=not SAVE.get("cheat_immortal",False); save_data(SAVE)
                elif key=="damage": SAVE["cheat_infinite_damage"]=not SAVE.get("cheat_infinite_damage",False); save_data(SAVE)
                elif key=="items":
                    SAVE["cheat_items_infinite"]=not SAVE.get("cheat_items_infinite",False)
                    save_data(SAVE)
                elif key=="max_chars":
                    self.cheat_max_all_characters()
                elif key=="max_perm":
                    self.cheat_max_permanent_upgrades()
                elif key=="passives":
                    self.open_passive_dev()
            elif self.cheat_clear_rect.collidepoint(pos):
                if self.cheat_money_mode or self.cheat_value_mode: self.cheat_money_buffer = self.cheat_money_buffer[:-1]
                else: self.cheat_buffer = self.cheat_buffer[:-1]
            elif self.cheat_confirm_rect.collidepoint(pos): self.submit_cheat()
            else:
                for r,digit in self.cheat_digit_rects:
                    if r.collidepoint(pos):
                        if (self.cheat_money_mode or self.cheat_value_mode) and len(self.cheat_money_buffer) < 9:
                            self.cheat_money_buffer += digit
                        elif not self.cheat_money_mode and not self.cheat_value_mode and len(self.cheat_buffer) < 8:
                            self.cheat_buffer += digit
                        break

        elif self.state == "backup":
            if self.backup_back_rect.collidepoint(pos):
                self.backup_stop_input(); self.state = "menu"
            elif self.backup_generate_rect.collidepoint(pos):
                self.generate_backup()
            elif self.backup_copy_rect.collidepoint(pos):
                self.copy_backup()
            elif self.backup_paste_rect.collidepoint(pos):
                self.paste_backup()
            elif self.backup_input_rect.collidepoint(pos):
                self.backup_start_input()
            elif self.backup_restore_rect.collidepoint(pos):
                self.restore_backup()
            elif self.backup_clear_rect.collidepoint(pos):
                self.backup_input = ""; self.backup_message = ""

        elif self.state == "vinicius_mega":
            for r,key in getattr(self,"vinicius_mega_choice_rects",[]):
                if r.collidepoint(pos): self.build_vinicius_mega(key); break

        elif self.state == "lira_domain_choice":
            for r,key in getattr(self,"lira_domain_choice_rects",[]):
                if r.collidepoint(pos): self.choose_lira_domain_stat(key); break

        elif self.state == "upgrade":
            if self.upgrade_confirm_rect.collidepoint(pos) and self.selected_upgrade_card is not None:
                self.apply_upgrade(self.selected_upgrade_card)
            else:
                for r, card in self.upgrade_rects:
                    if r.collidepoint(pos):
                        self.selected_upgrade_card = card
                        AUDIO.play("click", 0.6)
                        break

        elif self.state == "death":
            if self.death_retry_rect.collidepoint(pos):
                self.reset_run(self.selected_character)
            elif self.death_menu_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "menu"


def main():
    game = Game()
    running = True
    while running:
        dt = min(CLOCK.tick(FPS) / 1000.0, 0.033)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    if game.state == "menu":
                        running = False
                    elif game.state == "playing":
                        game.pause_game()
                    elif game.state == "paused":
                        game.state = "playing"
                    elif game.state == "run_upgrades":
                        game.state = "paused"
                    elif game.state == "vinicius_mega":
                        game.state="playing"
                    elif game.state == "difficulty_select":
                        game.state = "character_select"
                    elif game.state == "mode_select":
                        game.state = "menu"
                    elif game.state == "curse_choice":
                        pass
                    elif game.state == "mode_complete":
                        game.state = "menu"
                    elif game.state == "character_select":
                        game.state = "mode_select" if game.selection_target=="arena" else "menu"
                    elif game.state == "settings":
                        game.close_settings()
                    elif game.state == "passive_roll":
                        if not game.passive_roll_spinning:
                            game.passive_auto_mode=False; game.state = game.passive_roll_return_state
                    elif game.state == "passive_auto_config":
                        game.state="passive_roll"
                    elif game.state == "passive_dev":
                        game.state="cheats"
                    elif game.state in ("upgrade_catalog", "passive_catalog", "bestiary", "control_editor", "shop", "glonk_death", "death", "whats_new", "achievements", "missions", "cheats", "backup"):
                        if game.state == "control_editor":
                            game.control_editor_up()
                        if game.state == "backup":
                            game.backup_stop_input()
                        game.state = "menu"
                    else:
                        game.state = "menu"

                if event.key == pygame.K_p and game.state == "playing":
                    game.pause_game()
                elif event.key == pygame.K_p and game.state == "paused":
                    AUDIO.play("click", 0.6); game.state = "playing"
                # Volume agora e controlado exclusivamente em CONFIGURACOES.

                if game.state == "cheats":
                    if pygame.K_0 <= event.key <= pygame.K_9:
                        digit = chr(event.key)
                        if game.cheat_money_mode and len(game.cheat_money_buffer) < 9:
                            game.cheat_money_buffer += digit
                        elif not game.cheat_money_mode and len(game.cheat_buffer) < 8:
                            game.cheat_buffer += digit
                    elif event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                        if game.cheat_money_mode: game.cheat_money_buffer = game.cheat_money_buffer[:-1]
                        else: game.cheat_buffer = game.cheat_buffer[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        game.submit_cheat()

                if game.state == "backup" and game.backup_input_active:
                    if event.key in (pygame.K_BACKSPACE, pygame.K_DELETE):
                        game.backup_input = game.backup_input[:-1]
                    elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                        game.restore_backup()
                    elif event.key == pygame.K_v and (event.mod & pygame.KMOD_CTRL):
                        game.paste_backup()

                if game.state == "playing" and not getattr(game, "mahoraga_cutscene_active", False) and not getattr(game, "sukuna_cutscene_active", False):
                    if event.key == pygame.K_SPACE:
                        game.attack_held=True
                        if game.player.character == "Potential Man":
                            game.player.potential_hold_timer=0.0; game.player.potential_hold_triggered=False
                        elif game.player.uses_special_attack_hold():
                            if game.player.character==RIP_INDRA_KEY: game.player.rip_hold_time=0.0
                            else: game.player.hisoka_hold_time=0.0
                        elif game.player.has_divine_attack_hold():
                            game.player.divine_attack_hold=0.0; game.player.divine_attack_triggered=False
                        elif game.player.character == HANK_KEY:
                            # No teclado, segurar ESPACO prepara; o tiro sai no KEYUP.
                            pass
                        else:
                            game.player.attack(game)
                    elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        if game.player.divine_ruan or game.player.divine_kayk or game.player.divine_pedro:
                            game.dash_held=True; game.player.divine_dash_hold=0.0; game.player.divine_dash_triggered=False
                        else: game.player.dash(game, game.get_move_dir())
                    elif event.key == pygame.K_e:
                        if game.player.character == "Sans": game.player.fire_sans_blaster(game, auto=False)
                        elif game.player.divine_kevyn:
                            game.parry_held=True; game.player.divine_parry_hold=0.0; game.player.divine_parry_triggered=False
                        else: game.player.parry(game)
                    elif event.key == pygame.K_q:
                        if game.player.divine_kevyn:
                            game.domain_held=True; game.player.divine_domain_hold=0.0; game.player.divine_domain_triggered=False
                        elif game.player.character == HANK_KEY:
                            game.domain_held=True; game.player.hank_domain_hold=0.0; game.player.hank_domain_triggered=False
                        elif game.player.character == SUKUNA_KEY:
                            game.domain_held=True; game.player.sukuna_domain_hold=0.0; game.player.sukuna_domain_triggered=False
                        else: game.player.expand_domain(game)

            elif event.type == pygame.KEYUP:
                if game.state == "playing" and not getattr(game, "mahoraga_cutscene_active", False) and not getattr(game, "sukuna_cutscene_active", False):
                    if event.key == pygame.K_SPACE:
                        if game.player.character == HANK_KEY:
                            game.player.attack(game)
                        elif game.player.character == "Potential Man" and not game.player.potential_hold_triggered: game.player.attack(game)
                        elif game.player.uses_special_attack_hold(): game.player.finish_special_attack_hold(game)
                        elif game.player.has_divine_attack_hold(): game.player.finish_attack_hold(game)
                        game.player.potential_hold_timer=0.0; game.player.potential_hold_triggered=False; game.attack_held=False
                    elif event.key in (pygame.K_LSHIFT,pygame.K_RSHIFT) and game.dash_held:
                        game.dash_held=False; game.player.finish_dash_hold(game)
                    elif event.key == pygame.K_e and game.parry_held:
                        game.parry_held=False; game.player.finish_parry_hold(game)
                    elif event.key == pygame.K_q and game.domain_held:
                        game.domain_held=False; game.player.finish_domain_hold(game)

            elif event.type == pygame.TEXTINPUT:
                if game.state == "backup" and game.backup_input_active:
                    if len(game.backup_input) < 12000:
                        game.backup_input += event.text[:12000-len(game.backup_input)]

            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Em Pygame 2, toque pode gerar FINGER + MOUSE sintetico.
                if not getattr(event, "touch", False):
                    pos = to_game_pos(event.pos)
                    if game.state == "playing":
                        game.handle_touch_down(pos)
                    elif game.state == "control_editor":
                        game.control_editor_down(pos)
                    elif game.state == "character_select":
                        game.character_select_down(pos)
                    elif game.state == "whats_new":
                        game.whats_new_down(pos)
                    elif game.state == "settings":
                        game.settings_down(pos)
                    else:
                        game.click_ui(pos)

            elif event.type == pygame.MOUSEMOTION:
                if not getattr(event, "touch", False):
                    pos = to_game_pos(event.pos)
                    if game.state == "control_editor" and any(getattr(event, "buttons", (0, 0, 0))):
                        game.control_editor_motion(pos)
                    elif game.state == "playing" and any(getattr(event, "buttons", (0, 0, 0))):
                        game.handle_touch_motion(pos)
                    elif game.state == "character_select" and any(getattr(event, "buttons", (0, 0, 0))):
                        game.character_select_motion(pos)
                    elif game.state == "whats_new" and any(getattr(event, "buttons", (0, 0, 0))):
                        game.whats_new_motion(pos)
                    elif game.state == "settings" and any(getattr(event, "buttons", (0, 0, 0))):
                        game.settings_motion(pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if not getattr(event, "touch", False):
                    pos = to_game_pos(event.pos)
                    if game.state == "control_editor":
                        game.control_editor_up()
                    elif game.state == "character_select":
                        game.character_select_up(pos)
                    elif game.state == "whats_new":
                        game.whats_new_up(pos)
                    elif game.state == "settings":
                        game.settings_up(pos)
                    else:
                        game.handle_touch_up(pos)

            elif event.type == pygame.FINGERDOWN:
                physical = (event.x * PHYS_W, event.y * PHYS_H)
                pos = to_game_pos(physical)
                if game.state == "playing":
                    game.handle_touch_down(pos, event.finger_id)
                elif game.state == "control_editor":
                    game.control_editor_down(pos)
                elif game.state == "character_select":
                    game.character_select_down(pos, event.finger_id)
                elif game.state == "whats_new":
                    game.whats_new_down(pos)
                elif game.state == "settings":
                    game.settings_down(pos)
                else:
                    game.click_ui(pos)

            elif event.type == pygame.FINGERMOTION:
                physical = (event.x * PHYS_W, event.y * PHYS_H)
                pos = to_game_pos(physical)
                if game.state == "control_editor":
                    game.control_editor_motion(pos)
                elif game.state == "playing":
                    game.handle_touch_motion(pos, event.finger_id)
                elif game.state == "character_select":
                    game.character_select_motion(pos, event.finger_id)
                elif game.state == "whats_new":
                    game.whats_new_motion(pos)
                elif game.state == "settings":
                    game.settings_motion(pos)

            elif event.type == pygame.FINGERUP:
                physical = (event.x * PHYS_W, event.y * PHYS_H)
                pos = to_game_pos(physical)
                if game.state == "control_editor":
                    game.control_editor_up()
                elif game.state == "character_select":
                    game.character_select_up(pos, event.finger_id)
                elif game.state == "whats_new":
                    game.whats_new_up(pos)
                elif game.state == "settings":
                    game.settings_up(pos)
                else:
                    game.handle_touch_up(pos, event.finger_id)

        game.update(dt)
        game.draw()
        present_frame()

    save_data(SAVE)
    try:
        pygame.mixer.stop()
    except Exception:
        pass
    pygame.quit()


if __name__ == "__main__":
    main()
