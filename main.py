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

# ============================================================
# DERROTE O GORDO DO PAI DO KAYK - V14 WIP PERSONAGENS + EVOLUCAO
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

pygame.display.set_caption("Derrote o Gordo do Pai do Kayk")
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
META_ACH_COLOR = (255, 118, 230)

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
        self.sfx_on = bool(settings.get("sfx_on", True))
        self.music_on = bool(settings.get("music_on", True))
        self.sfx_volume = 0.72
        self.music_volume = 0.20
        self.current_track = None
        self.last_play = {}
        self.sfx = {}
        self.music = {}
        self.music_channel = None
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
        self.sfx_on = not self.sfx_on
        return self.sfx_on

    def toggle_music(self):
        self.music_on = not self.music_on
        if not self.music_on and self.enabled and self.music_channel:
            self.music_channel.stop()
            self.current_track = None
        return self.music_on

    def sync_music(self, game):
        if not self.enabled or self.music_channel is None:
            return
        if not self.music_on:
            if self.music_channel.get_busy():
                self.music_channel.stop()
            self.current_track = None
            return
        if game.state in ("playing", "paused", "run_upgrades", "vinicius_mega"):
            boss_alive = any(type(e).__name__ == "Boss" and not getattr(e, "dead", False) for e in game.enemies)
            target = "boss" if boss_alive else "arena"
            vol = self.music_volume * (0.42 if game.state in ("paused", "run_upgrades", "vinicius_mega") else 1.0)
        else:
            target = "menu"
            vol = self.music_volume * 0.82
        try:
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
    "Pai do Kayk": {
        "hp": 225, "stamina": 182, "weapon": 8, "weapon_name": "GOLPE EM AREA", "damage": 28.0, "speed": 270,
        "regen": 9.5, "color": (220, 220, 220), "domain": "AUTORIDADE PATERNA",
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
        "hp": 150, "stamina": 155, "weapon": 12, "weapon_name": "CAO DIVINO", "damage": 20.0, "speed": 292,
        "regen": 10.5, "color": (18, 18, 24), "domain": "MAHORAGA",
        "desc": "Beta | Invoca 2 Caes Divinos | ULT: Mahoraga",
        "domain_desc": "Invoca Mahoraga: adaptativo, resistente e perigoso para TODOS",
    },
    "Vinicius 13": {
        "hp": 138, "stamina": 150, "weapon": 13, "weapon_name": "AUTOMACAO V13", "damage": 12.0, "speed": 300,
        "regen": 10.5, "color": (220, 55, 70), "domain": "NENHUM",
        "desc": "Projeteis encadeados | Sucata Inimiga | Mini e Mega Torretas",
        "domain_desc": "Vinicius 13 troca Dominio por um sistema de construcao automatica.",
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
CHARACTER_ORDER = ["Ana", "Kevyn", "Ycaro", "Kayk", "Pedro", "Ruan", "Pai do Kayk", "Vinicius 13", "Glonk"]
BETA_CHARACTER_ORDER = ["Sans", "Strikada Egoísta", "Glonk 100% Power", "Potential Man"]
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
    "Pai do Kayk": {"strength":9,"speed":6,"resistance":9,"hp":9,"stamina":8,"parry":5},
    "Glonk": {"strength":1,"speed":1,"resistance":1,"hp":1,"stamina":1,"parry":1},
    "Strikada Egoísta": {"strength":8,"speed":8,"resistance":6,"hp":6,"stamina":7,"parry":6},
    "Glonk 100% Power": {"strength":1,"speed":6,"resistance":1,"hp":1,"stamina":4,"parry":2},
    "Sans": {"strength":7,"speed":9,"resistance":8,"hp":1,"stamina":10,"parry":9},
    "Potential Man": {"strength":7,"speed":7,"resistance":7,"hp":7,"stamina":7,"parry":6},
    "Vinicius 13": {"strength":5,"speed":7,"resistance":5,"hp":6,"stamina":7,"parry":5},
}

# Cartas: stats simples ficam comuns; cartas raras mudam a forma de jogar.
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
    ("rare", "MIRA CRITICA", "+12% chance de critico x2", "crit"),

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
    ],
    "Pedro": [
        ("rare", "FRUTA MADURA", "+30% dano dos abacaxis", "pedro_ripe_fruit"),
        ("rare", "TRAJETORIA ESPINHOSA", "+30% velocidade e alcance do bumerangue", "pedro_spiny_path"),
        ("rare", "IDA E VOLTA", "Dano na volta +35% (todo abacaxi ja pode acertar novamente)", "pedro_round_trip"),
        ("epic", "ABACAXI EXPLOSIVO", "Cada impacto causa dano em area", "pedro_explosive_pineapple"),
        ("epic", "DUPLA COLHEITA", "Ataques normais lancam +1 abacaxi", "pedro_double_harvest"),
        ("epic", "CASCA DE ACO", "Parry custa menos Estamina e dura mais", "pedro_steel_peel"),
        ("legendary", "COROA DO ABACAXI", "Acertos na volta causam dano critico aumentado", "pedro_pineapple_crown"),
        ("legendary", "X DO DESTINO", "Dominio tambem lanca nas 4 direcoes cardeais", "pedro_x_destiny"),
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
    ],
    "Strikada Egoísta": [
        ("rare", "REBOTE EGOISTA", "+2 inimigos no limite de quique da bola", "strikada_more_bounces"),
        ("rare", "VISAO DE GOL", "A bola corrige a rota e persegue o inimigo mais proximo", "strikada_homing"),
        ("epic", "DOIS PROTAGONISTAS", "Cada Chute Direto lanca duas bolas", "strikada_two_balls"),
        ("epic", "GOL DE IMPACTO", "Se a bola derrotar um inimigo, ele explode e causa dano em area", "strikada_kill_explosion"),
    ],
    "Glonk 100% Power": [],
    "Pai do Kayk": [
        ("rare", "ONDA PATERNA", "+25% raio do golpe em area", "father_wave"),
        ("rare", "PALMADA SISMICA", "+30% dano do golpe em area", "father_slap"),
        ("rare", "FOLEGO DE PAI", "+30 Estamina maxima", "father_lung"),
        ("epic", "AUTORIDADE", "Golpe em area apaga projeteis inimigos", "father_authority"),
        ("epic", "PROBLEMAS FAMILIARES", "+55% dano contra bosses", "father_family_issues"),
        ("epic", "PAI PRESENTE", "Derrotar boss recupera 30% do HP", "father_present"),
        ("legendary", "CIRCULO DA SENTENCA", "+35% raio da Expansao", "father_sentence_circle"),
        ("legendary", "PONTO FINAL", "Expansao tambem enche HP e Estamina", "father_final_word"),
    ],
    "Glonk": [],
}

STACKABLE_UPGRADES = {"heart_reinforced", "steel_lung", "second_wind", "heavy_hand", "quick_feet", "scavenger", "pierce", "crit"}

FATHER_UNLOCK_CHARACTERS = ["Ana", "Kevyn", "Ycaro", "Kayk", "Pedro", "Ruan"]

BOSS_VARIANTS = [
    {
        "key": "father", "name": "PAI DO KAYK", "color": (160, 50, 70),
        "domain": "CIRCULO DA DISCIPLINA",
        "domain_desc": "Ondas de autoridade causam dano periodico em quem ficar perto demais.",
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
    {"name":"PERSEGUIDOR", "type":"Inimigo", "hp":"1.15x HP base", "speed":"1.15x velocidade", "damage":"Contato: 7 + 0.7/onda", "desc":"Corre diretamente ate voce e tenta manter contato."},
    {"name":"ATIRADOR", "type":"Inimigo", "hp":"1.00x HP base", "speed":"0.72x velocidade", "damage":"Projetil: 7 + 0.55/onda", "desc":"Mantem distancia e dispara projeteis em intervalos regulares."},
    {"name":"KITER", "type":"Inimigo", "hp":"0.85x HP base", "speed":"1.05x velocidade", "damage":"2 projeteis: 5 + 0.45/onda", "desc":"Anda de lado, foge quando voce chega perto e atira em pares."},
    {"name":"TANQUE", "type":"Inimigo", "hp":"2.40x HP base", "speed":"0.58x velocidade", "damage":"Contato: 1.45x", "desc":"Lento, enorme e resistente. Excelente candidato a Execucao."},
    {"name":"ELITE: FRENESI", "type":"Mutacao", "hp":"HP do hospedeiro", "speed":"1.55x", "damage":"Normal", "desc":"Mutacao rosa extremamente rapida."},
    {"name":"ELITE: GIGANTE", "type":"Mutacao", "hp":"2.10x", "speed":"Normal", "damage":"1.30x contato", "desc":"Aumenta muito HP, tamanho e dano de contato."},
    {"name":"ELITE: BLINDADO", "type":"Mutacao", "hp":"1.65x HP", "speed":"Normal", "damage":"Normal", "desc":"Recebe apenas 72% do dano causado pelo jogador."},
    {"name":"ELITE: EXPLOSIVO", "type":"Mutacao", "hp":"HP normal", "speed":"Normal", "damage":"Explode em 8 projeteis", "desc":"Ao morrer dispara uma coroa de projeteis perigosos."},
    {"name":"PAI DO KAYK", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Contato alto + rajadas", "desc":"Boss da onda 5. Seu Dominio e CIRCULO DA DISCIPLINA."},
    {"name":"O DEVORADOR", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Contato + drenagem", "desc":"Seu Dominio ESTOMAGO SEM FUNDO devora Estamina e depois HP."},
    {"name":"A SENTINELA", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Controle por projeteis", "desc":"Seu Dominio OLHO DO CERCO cria disparos extras em cruz."},
    {"name":"REI DO VAZIO", "type":"Boss", "hp":"700 + 95/onda", "speed":"75 + onda", "damage":"Pressao de recursos", "desc":"SILENCIO ABSOLUTO reduz regeneracao e carga de Dominio."},
    {"name":"A GULA", "type":"Boss Especial", "hp":"Escala brutal + memoria de derrotas", "speed":"Aumenta a cada encontro", "damage":"Qualquer golpe que atravesse sua defesa encerra a run", "desc":"No novo ciclo V14, a Gula aparece primeiro na onda 80. Cada vez que devora um jogador, fica permanentemente mais forte nos reencontros."},
    {"name":"MINI-ANA", "type":"Invocacao", "hp":"Explode ao contato", "speed":"Persegue automaticamente", "damage":"Explosao da Ana", "desc":"Criada pelo cajado da Ana. Corre ate o alvo e explode em area."},
    {"name":"AMIGO DO RUAN", "type":"Invocacao", "hp":"Depende do inimigo recrutado", "speed":"Persegue inimigos", "damage":"Ataque automatico", "desc":"Nasce quando Ruan derrota diretamente um inimigo. Certas armas podem copiar completamente o inimigo derrotado."},
    {"name":"GUARDIAO DO RUAN", "type":"Invocacao", "hp":"Muito alto", "speed":"Alta", "damage":"Corpo a corpo pesado", "desc":"Guardiao criado pela Expansao de Ruan e preso a area do Dominio."},
    {"name":"CAES DIVINOS", "type":"Invocacao Beta", "hp":"HP proprio + regeneracao", "speed":"Alta", "damage":"Mordidas automaticas", "desc":"Dupla invocada pelo Potential Man ao segurar ATK. So enfrenta Mahoraga se o jogador provocar Mahoraga primeiro."},
    {"name":"MAHORAGA", "type":"Invocacao Beta", "hp":"Muito alto + cura por onda", "speed":"Boss", "damage":"Lamina do Exterminio", "desc":"Entidade neutra e adaptativa. Ataca inimigos e jogador; ganha 5% de resistencia por onda ate 70%."},
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
FORGE_CHARACTER_ORDER = ["Ana", "Kevyn", "Ycaro", "Kayk", "Pedro", "Ruan", "Pai do Kayk", "Glonk", "Sans", "Strikada Egoísta", "Glonk 100% Power", "Potential Man"]
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

    # PAI DO KAYK
    {"key":"father_sentence_fist","character":"Pai do Kayk","name":"PUNHO DA SENTENCA","rarity":"mythic","coins":2600,
     "cost":{"scrap":28,"core":12,"domain_crystal":6,"boss_heart":4},"desc":"Golpe em area fica 25% maior, causa +20% dano e apaga projeteis inimigos."},
    {"key":"father_scrap_glove","character":"Pai do Kayk","name":"LUVA IRRELEVANTE","rarity":"rare","coins":850,
     "cost":{"scrap":20,"essence":4},"desc":"+18% raio do golpe e +10% dano.","mods":{"father_radius":1.18,"damage":1.10}},
    {"key":"father_king_seal","character":"Pai do Kayk","name":"SELO DO REI","rarity":"legendary","coins":1800,
     "cost":{"core":8,"domain_crystal":4,"boss_heart":2},"desc":"+25% dano contra bosses, +20 HP e +1 escudo.","mods":{"father_boss":1.25,"hp":20,"shield":1}},
    {"key":"father_void_hand","character":"Pai do Kayk","name":"MAO DO VOID","rarity":"mythic","coins":2700,
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
     "cost":DIVINE_COST.copy(),"desc":"Se nao houver nenhum Amigo normal vivo, um DASH invoca 1 Amigo no ponto de partida. Segurar DASH 1s teleporta o dobro da distancia e segue a mesma regra. Amigos podem soltar orbes de +5 HP."},
    {"key":"pedro_hunting_time","character":"Pedro","name":"TEMPO DE CACA","rarity":"divine","coins":0,
     "cost":DIVINE_COST.copy(),"desc":"+100% velocidade. Abacaxis sao teleguiados e sempre recuperam HP/Estamina. Segurar DASH 1s planta um abacaxi que fere inimigos e cura 10 HP ao ser recolhido."},

    # PREVIAS DIVINAS BETA - aparecem no arsenal, mas nao podem ser forjadas/equipadas enquanto o personagem for Beta.
    {"key":"sans_final_judgement","character":"Sans","name":"JULGAMENTO DO ULTIMO ATALHO","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA BETA] Blasters atravessam a arena em cadeia e ossos ganham trajetorias impossiveis. Integracao reservada para a saida do Beta."},
    {"key":"strikada_absolute_ego","character":"Strikada Egoísta","name":"EGO ABSOLUTO: GOL IMPOSSIVEL","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA BETA] A bola reconhece todos os alvos da arena e transforma cada quique em uma nova rota de gol."},
    {"key":"glonk_over_100","character":"Glonk 100% Power","name":"101% POWER","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA BETA] Um equipamento absurdo para o ser de 1 HP e 1 de dano. Efeito final sera ativado quando sair do Beta."},
    {"key":"potential_totality","character":"Potential Man","name":"DEZ SOMBRAS: TOTALIDADE","rarity":"divine","coins":0,"cost":DIVINE_COST.copy(),"preview":True,
     "desc":"[PREVIA BETA] Cães, sapos e Mahoraga compartilham uma invocacao total. Integracao reservada para a saida do Beta."},

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
    ('wave_10', 'DEZ ONDAS', 'Alcance a onda 10.'),
    ('wave_25', 'VINTE E CINCO', 'Alcance a onda 25.'),
    ('wave_50', 'O MENSAGEIRO', 'Alcance a onda 50.'),
    ('wave_75', 'SETENTA E CINCO', 'Alcance a onda 75.'),
    ('wave_100', 'TRES DIGITOS', 'Alcance a onda 100.'),
    ('wave_150', 'UM LONGO CAMINHO', 'Alcance a onda 150.'),
    ('wave_200', 'DUZENTAS', 'Alcance a onda 200.'),
    ('wave_250', 'ISSO JA E PESSOAL', 'Alcance a onda 250.'),
    ('wave_300', 'TREZENTAS', 'Alcance a onda 300.'),
    ('wave_400', 'QUATROCENTAS', 'Alcance a onda 400.'),
    ('wave_500', 'ONDE TERMINA?', 'Alcance a onda 500.'),
    ('wave_600', 'SEISCENTAS', 'Alcance a onda 600.'),
    ('wave_700', 'SETE PECADOS', 'Alcance a onda 700.'),
    ('wave_850', 'AINDA AQUI?', 'Alcance a onda 850.'),
    ('wave_1000', 'MIL ONDAS', 'Alcance a onda 1000.'),
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
    ('clash_1', 'PRIMEIRO CHOQUE', 'Venca 1 Choque de Dominios no total.'),
    ('clash_3', 'TRES CHOQUES', 'Venca 3 Choques de Dominios no total.'),
    ('clash_5', 'CINCO CHOQUES', 'Venca 5 Choques de Dominios no total.'),
    ('clash_10', 'IMPERADOR DOS DOMINIOS', 'Venca 10 Choques de Dominios no total.'),
    ('clash_20', 'VINTE VITORIAS', 'Venca 20 Choques de Dominios no total.'),
    ('clash_35', 'TRINTA E CINCO', 'Venca 35 Choques de Dominios no total.'),
    ('clash_50', 'CINQUENTA CHOQUES', 'Venca 50 Choques de Dominios no total.'),
    ('clash_100', 'CEM VEZES SOBERANO', 'Venca 100 Choques de Dominios no total.'),
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
    ('father_unlock', 'PAI PRESENTE', 'Desbloqueie o Pai do Kayk.'),
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
    'wave_10': ('wave', 10),
    'wave_25': ('wave', 25),
    'wave_50': ('wave', 50),
    'wave_75': ('wave', 75),
    'wave_100': ('wave', 100),
    'wave_150': ('wave', 150),
    'wave_200': ('wave', 200),
    'wave_250': ('wave', 250),
    'wave_300': ('wave', 300),
    'wave_400': ('wave', 400),
    'wave_500': ('wave', 500),
    'wave_600': ('wave', 600),
    'wave_700': ('wave', 700),
    'wave_850': ('wave', 850),
    'wave_1000': ('wave', 1000),
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
    "Pai do Kayk": [
        ("father_kills_v12", "AUTORIDADE", "Derrote 4.000 inimigos com o Pai do Kayk", "kills", 4000, 3200),
        ("father_domains_v12", "SENTENCA", "Ative 300 Dominios com o Pai do Kayk", "domains", 300, 4000),
        ("father_wave_v12", "CHEFE DA CASA", "Alcance a onda 400 com o Pai do Kayk", "best_wave", 400, 7000),
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


WHATS_NEW = [
    'V13 FINAL: Vinicius 13 chegou com projeteis encadeados, Sucata Inimiga e sistema de torretas automaticas.',
    'FORJA: inimigos e bosses podem derrubar materiais; receitas usam materiais + moedas para fabricar equipamentos.',
    'ITENS e ARMAS: inventario separado por materiais, Pedacos dos Pecados e arsenal filtrado por personagem.',
    'RARIDADE DIVINA: armas azul-claro exigem 1 Pedaco de cada um dos sete Pecados e liberam mecanicas especiais.',
    'V14: Arcebispos e Pecados foram comprimidos — Ira começa em 35/40 e Luxuria fecha o ciclo em 95/100; depois o ciclo reinicia mais forte.',
    'BOSSES: o antigo endgame foi comprimido; a wave 100 agora escala aproximadamente como a antiga wave 700.',
    'PERSONAGENS: carrossel, fichas detalhadas, nivel e Pontos de Evolucao individuais para personagens normais.',
    'BETA: Sans, Strikada Egoista, Glonk 100% Power e Potential Man seguem em sandbox sem progresso persistente.',
    'BESTIARIO: agora possui TREINAMENTO para enfrentar inimigos, bosses e Pecados escolhidos sem progresso ou loot.',
    'LOJA PERMANENTE: todos os upgrades agora possuem limite maximo de LV.30.',
    'V14 WIP: armas Divinas de Kevyn, Ruan e Pedro foram retrabalhadas; cada onda agora concede 1 Ponto de Evolucao garantido.',
    'V14 WIP: cinco dificuldades chegaram — Facil preserva o jogo original; Medio, Dificil, Monarca e IMPOSSIVEL escalam inimigos e reduzem recompensas.',
    'V14 WIP: velocidade por wave foi suavizada; HP, dano, quantidade e IA continuam com a progressao comprimida. Painel DEV ganhou atalhos de maximizacao.',
    'HUD: cooldowns de ataque, Dash, Parry/Blaster e habilidades especiais aparecem no canto.',
    'CONQUISTAS: 100 desafios com barras individuais e progresso geral, terminando em Nao e dificil, so e chato.',
    'PAINEL DEV: inclui dinheiro, Pontos de Evolucao, onda inicial, imortalidade, dano infinito e itens infinitos.',
    'NOVIDADES: lista completa pode ser arrastada e possui efeito elastico no inicio e no fim.',
    'BACKUP: exportacao/restauracao de progresso e clipboard nativo Android continuam incluidos.',
]



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
    "kayk_unlocked": False,
    "father_victories": [],
    "father_unlocked": False,
    "cheat_all_chars": False,
    "unlocked_achievements": [],
    "mission_stats": {},
    "completed_missions": [],
    "total_kills": 0,
    "total_domains": 0,
    "clash_wins": 0,
    "pineapple_refunds": 0,
    "gula_hunger": 0,
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
    "control_layout": {},
    "sfx_on": True,
    "music_on": True,
}


def load_save():
    try:
        with open(SAVE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        out = DEFAULT_SAVE.copy()
        out.update(data)
        return out
    except Exception:
        return DEFAULT_SAVE.copy()


def save_data(data):
    try:
        with open(SAVE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


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
        self.base_speed = S(560) * speed_mult
        super().__init__(player.pos + d*S(40), d*self.base_speed, damage, "player", S(15), YELLOW, 4.0, 1)
        self.kind = "pineapple"
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

    def update(self, dt):
        self.life -= dt
        self.spin += dt * 9.0
        if self.life <= 0:
            return False
        if not self.returning:
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


class RuanServant:
    """Amigo criado por um abate DIRETO do Ruan."""
    NEXT_ID = 1
    def __init__(self, pos, source_enemy, player, guardian=False):
        self.id = RuanServant.NEXT_ID
        RuanServant.NEXT_ID += 1
        self.pos = pygame.Vector2(pos)
        self.guardian = guardian
        self.dead = False
        self.radius = S(58 if guardian else 24)
        base_hp = max(35.0, min(280.0, getattr(source_enemy, "max_hp", 70) * (0.52 if not guardian else 1.15)))
        self.max_hp = base_hp * player.ruan_servant_hp_mult
        self.hp = self.max_hp
        self.damage = max(9.0, player.base_damage * (2.20 if guardian else 0.58)) * player.ruan_servant_damage_mult
        if guardian:
            self.damage *= player.ruan_guardian_mult
            self.max_hp *= player.ruan_guardian_mult
            self.hp = self.max_hp
        self.speed = S(210 if guardian else 165) * player.ruan_servant_speed_mult
        self.attack_cd = 0.0
        self.color = CYAN if guardian else GREEN
        self.forge_exact_clone = bool(getattr(player, "forge_ruan", False) and not guardian and hasattr(source_enemy, "kind"))
        if self.forge_exact_clone:
            self.radius = getattr(source_enemy, "radius", self.radius)
            self.max_hp = max(1.0, getattr(source_enemy, "max_hp", self.max_hp))
            self.hp = self.max_hp
            self.speed = getattr(source_enemy, "speed", self.speed)
            self.damage = max(1.0, getattr(source_enemy, "contact_damage", self.damage))
            self.color = getattr(source_enemy, "color", self.color)
            self.clone_kind = getattr(source_enemy, "kind", "chaser")
            self.clone_elite = getattr(source_enemy, "elite", None)
        self.shield_hits = 2 if (player.ruan_growing_army and not guardian) else (5 if guardian else 0)
        self.divine_orb = bool(getattr(player,"divine_ruan",False) and not guardian)

    def take_damage(self, amount, game):
        if self.dead:
            return
        if self.shield_hits > 0:
            self.shield_hits -= 1
            game.spawn_particles(self.pos, BLUE, 5)
            return
        self.hp -= amount
        game.spawn_particles(self.pos, self.color, 4)
        if self.hp <= 0:
            self.dead = True
            game.spawn_particles(self.pos, GRAY, 12)

    def update(self, dt, game):
        if self.dead:
            return False
        self.attack_cd = max(0.0, self.attack_cd-dt)
        # Amigos normais perdem vida aos poucos; guardiao continua preso a duracao do Dominio.
        if not self.guardian:
            self.hp -= self.max_hp * 0.025 * dt
            if self.hp <= 0:
                self.dead = True
                game.spawn_particles(self.pos, GRAY, 10)
                return False
        targets = [e for e in game.enemies if not e.dead]
        if self.guardian:
            targets = [e for e in targets if game.is_in_domain(e.pos)]
        if not targets:
            return True
        target = min(targets, key=lambda e: e.pos.distance_to(self.pos))
        delta = target.pos - self.pos
        dist = max(1.0, delta.length())
        d = delta / dist
        if dist > self.radius + target.radius + S(12):
            self.pos += d * self.speed * dt
        elif self.attack_cd <= 0:
            old = game.current_damage_kind
            game.current_damage_kind = "ruan_guardian" if self.guardian else "ruan_servant"
            target.damage(self.damage, game, self.pos)
            game.current_damage_kind = old
            self.attack_cd = 0.38 if self.guardian else 0.72
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
                if random.random() < game.player.crit_chance:
                    dmg *= 2
                    game.damage_texts.append(DamageText("CRIT!", pygame.Vector2(enemy.pos), YELLOW))
                enemy.damage(dmg, game, self.pos)
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
        game.shake = max(game.shake, S(8))

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
        target = min(targets, key=lambda e: e.pos.distance_to(self.pos))
        direction = target.pos - self.pos
        dist = direction.length()
        if dist <= target.radius + self.radius + S(10):
            self.explode(game)
            return False
        if dist > 0:
            speed = self.speed
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
        # Longinus: cada Ana orbital e um unico acerto. Encostou, elimina o alvo e some.
        for e in list(game.enemies):
            if not e.dead and e.pos.distance_to(self.pos)<=e.radius+S(15):
                e.hp=0
                e.die(game)
                self.dead=True
                game.spawn_particles(self.pos,DIVINE_BLUE,5)
                return False
        maho=getattr(game,"mahoraga",None)
        if maho is not None and not maho.dead and maho.pos.distance_to(self.pos)<=maho.radius+S(15):
            maho.take_damage(maho.max_hp,game,self.pos,from_player=True)
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
        self.hp-=amount
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
        self.id=ViniciusTurret.NEXT_ID; ViniciusTurret.NEXT_ID+=1; self.pos=pygame.Vector2(pos); self.kind=kind; self.mega=mega; self.dead=False; self.taunt=False
        self.radius=S(72 if mega else 34); self.max_hp=(760 if mega else 125)+player.max_hp*(0.55 if mega else 0.16); self.hp=self.max_hp; self.damage=max(5.0,player.base_damage*(1.45 if mega else 0.72)); self.cd=random.uniform(0.15,0.8)
    def take_damage(self,amount,game):
        if self.dead:return
        self.hp-=amount
        if self.hp<=0: self.dead=True; game.spawn_particles(self.pos,self.COLORS.get(self.kind,WHITE),18); game.damage_texts.append(DamageText("TORRE DESTRUIDA",pygame.Vector2(self.pos),RED,0.8))
    def heal(self,amount):
        if not self.dead:self.hp=min(self.max_hp,self.hp+amount)
    def update(self,dt,game):
        if self.dead:return False
        self.cd-=dt; targets=[e for e in game.enemies if not e.dead]
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
        self.coin_value = 2

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

    def damage(self, amount, game, source_pos=None, minimal_fx=False):
        if self.dead:
            return
        if self.elite == "armored":
            amount *= 0.72
        self.hp -= amount
        if hasattr(game, "record_clash_damage"):
            game.record_clash_damage(amount)
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
        reward = int(self.coin_value * game.coin_multiplier * reward_mult * (1.0 + 0.05 * SAVE.get("coin_level", 0)))
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

        # Chuva de Orbes garante uma orb principal em elite.
        guaranteed = self.elite and game.player.orb_rain
        if guaranteed:
            game.drops.append(Drop(self.pos, random.choice(["heal", "stamina"])))

        bonus_each = game.player.drop_bonus * 0.5
        heal_chance = min(0.32, 0.14 + bonus_each)
        stamina_chance = min(0.32, 0.14 + bonus_each)
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
        self.forge_slow_timer = max(0.0, getattr(self, "forge_slow_timer", 0.0) - dt)
        move_speed = self.speed * (0.55 if self.forge_slow_timer > 0 else 1.0)
        self.shoot_cd -= dt
        self.touch_cd -= dt

        target_entity = game.get_enemy_target(self.pos)
        to_player = target_entity.pos - self.pos
        dist = max(1, to_player.length())
        direction = to_player / dist

        if self.kind == "chaser" or self.kind == "tank":
            self.pos += direction * move_speed * dt
        elif self.kind == "shooter":
            if dist > S(470):
                self.pos += direction * move_speed * dt
            elif dist < S(300):
                self.pos -= direction * move_speed * dt
            if self.shoot_cd <= 0:
                dcfg = difficulty_cfg(getattr(game, "difficulty", "easy")) if game.mode == "arena" else DIFFICULTIES["easy"]
                cw = effective_combat_wave(game.wave)
                speed = S(300 + cw * 5) * min(1.45, 1.0 + (dcfg["ai"]-1.0)*0.28)
                game.projectiles.append(Projectile(self.pos, direction * speed, (7 + cw * 0.55) * self.high_wave_damage_scale * dcfg["damage"], "enemy"))
                self.shoot_cd = max(0.22, (max(0.38, 1.45 - cw * 0.02)) / dcfg["ai"])
        elif self.kind == "kiter":
            tangent = pygame.Vector2(-direction.y, direction.x)
            if dist < S(360):
                move = -direction * 0.8 + tangent * 0.65
            else:
                move = direction * 0.35 + tangent * 0.8
            if move.length_squared() > 0:
                self.pos += move.normalize() * move_speed * dt
            if self.shoot_cd <= 0:
                for off in (-0.12, 0.12):
                    a = math.atan2(direction.y, direction.x) + off
                    dcfg = difficulty_cfg(getattr(game, "difficulty", "easy")) if game.mode == "arena" else DIFFICULTIES["easy"]
                    shot_speed = S(330) * min(1.45, 1.0 + (dcfg["ai"]-1.0)*0.28)
                    cw = effective_combat_wave(game.wave)
                    game.projectiles.append(Projectile(self.pos, vec_from_angle(a) * shot_speed, (5 + cw * 0.45) * self.high_wave_damage_scale * dcfg["damage"], "enemy", S(8), YELLOW))
                dcfg = difficulty_cfg(getattr(game, "difficulty", "easy")) if game.mode == "arena" else DIFFICULTIES["easy"]
                self.shoot_cd = 1.8 / dcfg["ai"]

        # contato: amigos do Ruan podem realmente proteger o jogador e receber golpes.
        if dist < self.radius + target_entity.radius and self.touch_cd <= 0:
            target_entity.take_damage(self.contact_damage, game)
            self.touch_cd = 0.75
            if target_entity is game.player and direction.length_squared() > 0:
                game.player.pos += direction * S(28) * getattr(self,"difficulty_force",1.0)

        self.pos.x = clamp(self.pos.x, self.radius, W - self.radius)
        self.pos.y = clamp(self.pos.y, S(165) + self.radius, H - S(335) - self.radius)

    def draw(self, offset):
        p = self.pos + offset
        color = WHITE if self.flash > 0 else self.color
        pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius)
        pygame.draw.circle(SCREEN, DARK, (int(p.x), int(p.y)), max(2, self.radius // 3), S(3))
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
            draw_text("PRESA", FONT_S, RED, (p.x, p.y + self.radius + S(44)), True)


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
        killer_character = game.player.character
        super().die(game)
        if not was_father or is_beta_character(killer_character):
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
            game.unlock_notice = f"PAI DO KAYK: {len(victories)}/{len(FATHER_UNLOCK_CHARACTERS)} PERSONAGENS"
            game.unlock_notice_timer = 5.0

        if all(name in victories for name in FATHER_UNLOCK_CHARACTERS) and not SAVE.get("father_unlocked", False):
            SAVE["father_unlocked"] = True
            changed = True
            AUDIO.play("unlock", 1.0)
            game.unlock_notice = "PAI DO KAYK DESBLOQUEADO!"
            game.unlock_notice_timer = 6.0
            game.unlock_achievement("father_unlock")

        if changed:
            save_data(SAVE)

    def update(self, dt, game):
        if self.dead:
            return
        self.flash = max(0, self.flash - dt)
        self.forge_slow_timer = max(0.0, getattr(self, "forge_slow_timer", 0.0)-dt)
        boss_move_speed = self.speed * (0.55 if self.forge_slow_timer > 0 else 1.0)
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
                    game.player.take_damage((6 + self.wave*0.22) * self.boss_damage_scale * difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], game)
                    game.damage_texts.append(DamageText("DISCIPLINA!", pygame.Vector2(game.player.pos), RED))
                    self.domain_tick = 0.95
                elif self.variant == "devourer" and inside:
                    drain = (16 + self.wave*0.12) * dt
                    if game.player.stamina > 0:
                        game.player.stamina = max(0, game.player.stamina-drain)
                    elif self.domain_tick <= 0:
                        game.player.take_damage((5 + self.wave*0.15) * self.boss_damage_scale * difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], game)
                        self.domain_tick = 0.8
                elif self.variant == "sentinel" and inside and self.domain_tick <= 0:
                    for i in range(4):
                        d = vec_from_angle(i*math.pi/2)
                        game.projectiles.append(Projectile(self.domain_center, d*S(355), (6+self.wave*0.35) * self.boss_damage_scale * difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], "enemy", S(9), CYAN, 2.5))
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
                game.projectiles.append(Projectile(self.pos, vec_from_angle(a) * S(285 if phase2 else 235), (8 + self.wave * 0.5)*buff*self.boss_damage_scale*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], "enemy", S(11), PINK))
            ai_mult = difficulty_cfg(getattr(game,"difficulty","easy"))["ai"] if game.mode=="arena" else 1.0
            self.burst_cd = (1.15 if phase2 else 1.9) / ai_mult
            game.shake = max(game.shake, S(5))

        if dist < self.radius + target_entity.radius and self.touch_cd <= 0:
            if self.variant == "gula" and target_entity is game.player:
                game.gula_devour(self)
            else:
                target_entity.take_damage((14 + self.wave * 0.8)*buff*self.boss_damage_scale*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"], game)
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
        # Pecados usam suas proprias mecanicas em vez dos Dominios aleatorios dos bosses comuns.
        self.domain_active=False; self.domain_cd=999999.0
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
        if self.sin_key == "pride" and self.pride_guard > 0:
            amount *= 0.28 if not self.archbishop else 0.45
        super().damage(amount, game, source_pos, minimal_fx)

    def update(self, dt, game):
        if self.dead: return
        self.sin_tick -= dt; self.sin_aux -= dt
        self.pride_guard=max(0.0,self.pride_guard-dt)
        # Pecado da Preguica: aura azul desacelera o jogador.
        if self.sin_key == "sloth" and self.pos.distance_to(game.player.pos) <= S(560):
            game.sin_sloth_slow = True
        super().update(dt, game)
        if self.dead: return
        strength = 0.60 if self.archbishop else 1.0
        diff_ai = difficulty_cfg(getattr(game,"difficulty","easy"))["ai"] if game.mode=="arena" else 1.0
        if self.sin_key == "wrath" and self.sin_tick <= 0:
            shots = 8 if self.archbishop else (12 if self.hp > self.max_hp*0.5 else 18)
            for i in range(shots):
                d=vec_from_angle(i*math.tau/shots + game.time*0.2)
                game.projectiles.append(Projectile(self.pos,d*S(330), (8+effective_combat_wave(game.wave)*0.22)*self.boss_damage_scale*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(9),RED,2.5))
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
                    game.projectiles.append(Projectile(self.pos,vec_from_angle(a+off)*S(390),(9+effective_combat_wave(game.wave)*0.20)*self.boss_damage_scale*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(10),GREEN,3.0))
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
                game.projectiles.append(Projectile(self.pos,d*S(205),(7+effective_combat_wave(game.wave)*0.16)*self.boss_damage_scale*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(13),BLUE,4.0))
            self.sin_tick=(2.4 if self.archbishop else 1.7) / diff_ai
        elif self.sin_key == "lust" and self.sin_aux <= 0:
            # Sem conteudo sexual: mecanica e uma ilusao violeta que teleporta o boss e cria um leque de projeteis.
            to=game.player.pos-self.pos
            if to.length_squared()>0:
                d=to.normalize(); self.pos=game.player.pos-d*S(330)
                a=math.atan2(d.y,d.x)
                for off in (-0.42,-0.21,0,0.21,0.42):
                    game.projectiles.append(Projectile(self.pos,vec_from_angle(a+off)*S(360),(8+effective_combat_wave(game.wave)*0.18)*self.boss_damage_scale*strength*difficulty_cfg(getattr(game,"difficulty","easy"))["damage"],"enemy",S(9),PINK,3.0))
            self.sin_aux=(3.4 if self.archbishop else 2.25) / diff_ai

    def die(self, game):
        if self.dead: return
        Enemy.die(self, game)
        if self.archbishop or game.mode != "arena" or is_beta_character(game.player.character):
            return
        # O fragmento vai direto ao inventario para nao ser perdido quando a onda terminar.
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
        game.unlock_notice=f"PEDACO DO PECADO: {self.sin_name}"
        game.unlock_notice_timer=4.5

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
        # Usa Enemy.die diretamente para nao acionar desbloqueios do Pai do Kayk.
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
        self.damage = max(8.0, player.base_damage * 0.62)
        self.speed = S(205)
        self.attack_cd = 0.0
        self.dead = False
        self.guardian = False
        self.color = (235,235,242) if side > 0 else (72,76,88)

    def take_damage(self, amount, game):
        if self.dead: return
        self.hp -= max(0.0, amount)
        game.spawn_particles(self.pos, self.color, 4)
        if self.hp <= 0:
            self.dead = True
            self.hp = 0
            others = [x for x in game.potential_summons if isinstance(x, DivineDog) and x is not self and not x.dead]
            if not others and game.player.character == "Potential Man":
                game.player.potential_dog_cd = max(game.player.potential_dog_cd, 7.0)
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
        self.wave_adaptations=0
        self.color=(220,220,205)
        self.slash_fx=0.0
        self.facing=pygame.Vector2(1,0)

    def take_damage(self, amount, game, source_pos=None, from_player=False):
        if self.dead:return
        self.hp -= max(0.0,amount)*(1.0-self.resistance)
        if from_player:
            if not getattr(game, "mahoraga_hostile_to_dogs", False):
                game.damage_texts.append(DamageText("MAHORAGA PROVOCADO", pygame.Vector2(self.pos), PINK, 0.65))
            game.mahoraga_hostile_to_dogs = True
        game.spawn_particles(self.pos,self.color,4)
        if self.hp<=0:
            self.hp=0; self.dead=True
            game.damage_texts.append(DamageText("MAHORAGA CAIU",pygame.Vector2(self.pos),GRAY,1.0))

    def end_wave_adapt(self, game):
        if self.dead:return
        self.wave_adaptations += 1
        self.resistance=min(0.70,self.resistance+0.05)
        self.hp=self.max_hp
        game.damage_texts.append(DamageText(f"ADAPTACAO {int(self.resistance*100)}%",pygame.Vector2(self.pos),YELLOW,1.0))

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
                game.player.take_damage(max(12.0,min(60.0,12.0+game.wave*0.08)),game); hit=True
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
        # Beta usa valores-base fixos: nao recebe nem aplica pontos de evolucao.
        evo = evolution_profile(self.character) if not is_beta_character(self.character) else {key: 0 for key in EVOLUTION_STAT_KEYS}
        self.evolution = evo
        self.evo_resistance = evo.get("resistance", 0)
        self.evo_parry = evo.get("parry", 0)
        self.base_speed = S(cfg["speed"]) * (1 + 0.03 * SAVE["speed_level"]) * (1 + 0.015 * evo.get("speed", 0))
        self.speed_mult = 1.0
        self.speed_buff = 0
        self.still_timer = 0.0

        self.max_hp = cfg["hp"] + SAVE["vitality_level"] * 8 + evo.get("hp", 0) * 6
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
        self.crit_chance = min(0.20, 0.02 * SAVE.get("crit_level", 0))
        self.drop_bonus = 0.02 * SAVE.get("orb_level", 0)
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

        # Ana
        self.ana_blind_spot = False
        self.ana_double_shot = False
        self.ana_reality_error = 0.0
        self.ana_vector_step = False
        self.ana_causal_eye = False
        self.ana_reality_exe = False
        # Kevyn
        self.kevyn_sword_range = 1.0
        self.kevyn_sword_cost_reduction = 0
        self.kevyn_sword_bonus = 1.0
        self.kevyn_human_wall = False
        self.kevyn_time_counter = False
        self.kevyn_immovable = False
        self.kevyn_hungry_sword = False
        self.kevyn_time_stops = False
        # Ycaro
        self.ycaro_point_blank = False
        self.ycaro_extra_pellets = 0
        self.ycaro_pellet_speed = 1.0
        self.ycaro_domino = False
        self.ycaro_aggressive_reload = False
        self.ycaro_sawed_off = False
        self.ycaro_hunter = False
        self.ycaro_no_too_close = False
        # Kayk
        self.kayk_extra_pair = 0
        self.kayk_soul_pierce = 0
        self.kayk_spectral_step = False
        self.kayk_pistol_bonus = 1.0
        self.kayk_armed_procession = False
        self.kayk_thousand_souls = False
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
        # Pai do Kayk jogavel
        self.father_radius_mult = 1.0
        self.father_damage_mult = 1.0
        self.father_clear_projectiles = False
        self.father_boss_bonus = False
        self.father_boss_weapon_mult = 1.0
        self.father_boss_heal = False
        self.father_domain_radius_mult = 1.0
        self.father_domain_refill = False
        # Sans beta
        self.is_moving = False
        self.sans_exhausted = False
        self.sans_blaster_cd = 0.0
        self.sans_melee_fx = 0.0
        self.sans_melee_dir = pygame.Vector2(1, 0)
        self.sans_dodge_cost = max(8.0, 20.0 * max(0.625, 1.0 - 0.015*self.evo_resistance))
        # Strikada Egoista
        self.strikada_bounces = 4
        self.strikada_extra_balls = 0
        self.strikada_homing = False
        self.strikada_kill_explosion = False
        # Glonk 100% Power
        self.glonk_power_fx = 0.0
        # Vinicius 13
        self.vinicius_phrase_cd = 0.0
        # Potential Man beta
        self.potential_dog_cd = 0.0
        self.potential_hold_timer = 0.0
        self.potential_hold_triggered = False
        self.potential_frog_fx = 0.0
        self.potential_frog_dir = pygame.Vector2(1, 0)

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

    def in_domain(self, game):
        return game.domain_active and self.pos.distance_to(game.domain_center) <= game.domain_radius

    def spend_stamina(self, amount):
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
        if game and getattr(game, "healing_locked", False):
            return
        old = self.hp
        amount *= 1.0 + 0.04 * SAVE.get("healing_level", 0)
        self.hp = clamp(self.hp + amount, 0, self.max_hp)
        if game and self.hp > old:
            game.damage_texts.append(DamageText("+" + str(int(self.hp-old)) + " HP", pygame.Vector2(self.pos), GREEN))

    def effective_damage_mult(self, game, enemy=None, source="generic", distance=None):
        m = self.damage_mult * game.player_event_damage_mult
        if SAVE.get("cheat_infinite_damage", False):
            m *= 1000000.0
        if self.overclock and self.stamina >= self.max_stamina * 0.80:
            m *= 1.20
        if self.predator_timer > 0:
            m *= 1.25
        if self.god_not_watching and self.hp <= self.max_hp * 0.20:
            m *= 1.65
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
        if self.character == "Pai do Kayk" and source == "father_wave":
            m *= self.father_damage_mult
            if isinstance(enemy, Boss):
                m *= self.father_boss_weapon_mult
                if self.father_boss_bonus:
                    m *= 1.55
        return m

    def take_damage(self, amount, game):
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
        self.hp -= amount
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
        self.invuln = 0.55
        if self.hp <= 0:
            if not self.revive_used and (self.second_bar or self.one_last_game):
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
        self.kayk_builder_wave_used=game.wave; self.hp=self.max_hp; self.stamina=self.max_stamina
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

    def finish_attack_hold(self, game):
        if not self.has_divine_attack_hold(): return
        if not self.divine_attack_triggered:
            self.attack(game)
        self.divine_attack_hold=0.0; self.divine_attack_triggered=False; self.longinus_next_threshold=2.0

    def finish_parry_hold(self, game):
        if self.divine_kevyn and not self.divine_parry_triggered: self.parry(game)
        self.divine_parry_hold=0.0; self.divine_parry_triggered=False

    def finish_domain_hold(self, game):
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
                if hit_any: game.register_combo_hit()
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
                game.projectiles.append(pr)
                self.attack_cd=0.56
            AUDIO.play("kevyn_sword",0.45,70)
            return

        # Potential Man beta: toque no ATK = Sapos em cone. Segurar 3s = Caes Divinos.
        if self.character == "Potential Man":
            self.potential_frog_attack(game)
            return

        # Vinicius 13: projetil vermelho retangular, levemente teleguiado e com espalhamento em ate 3 alvos.
        if self.character == "Vinicius 13":
            if not self.spend_stamina(4): return
            self.attack_cd=0.46
            d=pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
            pr=Projectile(self.pos+d*S(34),d*S(700),self.base_damage*0.72*self.projectile_bonus,"player",S(8),RED,2.3,0)
            pr.kind="vinicius_bolt"; pr.origin=pygame.Vector2(self.pos); pr.vinicius_child=False; game.projectiles.append(pr)
            game.damage_texts.append(DamageText(random.choice(VINICIUS_QUOTES),pygame.Vector2(self.pos.x,self.pos.y-S(70)),RED,1.05))
            AUDIO.play("kayk_dual",0.42,80); return

        # Strikada Egoista: Chute Direto na direcao atual. A bola comeca reta e, ao acertar,
        # procura o proximo alvo ate o limite de inimigos. Dentro do Dominio, o quique nao acaba.
        if self.character == "Strikada Egoísta":
            if not self.spend_stamina(7):
                return
            self.attack_cd = 3.5
            base_d = pygame.Vector2(self.facing) if self.facing.length_squared() else pygame.Vector2(1,0)
            base_a = math.atan2(base_d.y, base_d.x)
            count = 1 + self.strikada_extra_balls
            offsets = [0.0] if count == 1 else [-0.10, 0.10]
            for off in offsets:
                d = vec_from_angle(base_a + off)
                pr = Projectile(self.pos + d*S(38), d*S(620), self.base_damage*self.projectile_bonus,
                                "player", S(16), (125,220,255), 6.0, 0)
                pr.kind = "strikada_ball"
                pr.origin = pygame.Vector2(self.pos)
                pr.strikada_hits_left = self.strikada_bounces
                pr.strikada_homing = self.strikada_homing
                pr.strikada_kill_explosion = self.strikada_kill_explosion
                game.projectiles.append(pr)
            AUDIO.play("ycaro_shotgun",0.42,80)
            return

        # Glonk 100% Power: um ataque corpo a corpo ridiculamente simples de 1 de dano base.
        if self.character == "Glonk 100% Power":
            self.attack_cd = 0.46
            self.glonk_power_fx = 0.14
            rng = S(92)
            hit_any = False
            for e in list(game.enemies):
                if e.dead:
                    continue
                to_e = e.pos-self.pos
                dist = to_e.length()
                if dist <= rng + e.radius:
                    if dist <= 0.001 or (to_e/dist).dot(self.facing) >= math.cos(math.radians(80)):
                        old=game.current_damage_kind; game.current_damage_kind="glonk_100"
                        e.damage(self.base_damage*self.effective_damage_mult(game,e,"glonk_100",dist),game,self.pos)
                        game.current_damage_kind=old
                        hit_any=True
            maho=getattr(game,"mahoraga",None)
            if maho is not None and not maho.dead:
                to_m=maho.pos-self.pos; md=to_m.length()
                if md <= rng+maho.radius and (md <= 0.001 or (to_m/md).dot(self.facing) >= math.cos(math.radians(80))):
                    maho.take_damage(self.base_damage*self.effective_damage_mult(game,None,"glonk_100",md),game,self.pos,from_player=True)
                    hit_any=True
            if hit_any:
                game.register_combo_hit()
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
            rng = S(122) * self.kevyn_sword_range * (1.20 if kevyn_domain_evo else 1.0)
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
                        if random.random() < self.crit_chance:
                            dmg *= 2
                            game.damage_texts.append(DamageText("CRIT!", pygame.Vector2(e.pos), YELLOW))
                        game.current_damage_kind = "sword"
                        e.damage(dmg, game, self.pos)
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
                pr.kind="kevyn_divine_slash"; pr.origin=pygame.Vector2(self.pos); game.projectiles.append(pr)
            AUDIO.play("kevyn_sword", 0.72, 90)
            game.slash_fx = 0.12
            if hit_any:
                game.register_combo_hit()
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
            base_angle = math.atan2(self.facing.y, self.facing.x) - math.pi/2
            triangle_angles = [base_angle, base_angle + math.tau/3, base_angle + 2*math.tau/3]
            # 1 e 2 invocacoes ocupam vertices diferentes; 3 fecha o triangulo inteiro.
            chosen = triangle_angles if count == 3 else (triangle_angles[:1] if count == 1 else [triangle_angles[0], triangle_angles[2]])
            for i, ang in enumerate(chosen):
                spawn = self.pos + vec_from_angle(ang) * S(42)
                summon = MiniAna(
                    spawn,
                    self.base_damage * 1.55 * self.projectile_bonus,
                    i, count,
                    self.ana_miniana_speed,
                    self.ana_blast_mult,
                    self.ana_reality_error,
                )
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
            pairs = 1 + self.kayk_extra_pair
            base_a = math.atan2(self.facing.y, self.facing.x)
            # Dentro do Dominio: cada rajada ganha +1 bala e os projeteis ficam 35% mais rapidos.
            offsets = (-0.075, 0.0, 0.075) if kayk_domain else (-0.055, 0.055)
            kayk_shot_speed = 1.35 if kayk_domain else 1.0
            for pair in range(pairs):
                pair_shift = (pair - (pairs-1)/2) * 0.08
                for off in offsets:
                    d = vec_from_angle(base_a + off + pair_shift)
                    pr = Projectile(self.pos + d*S(36), d*S(790)*kayk_shot_speed, self.base_damage*0.78*self.projectile_bonus, "player", S(7), PURPLE, 2.0, self.projectile_pierce + self.kayk_soul_pierce)
                    pr.kind = "dual_pistol"
                    pr.forge_kayk = self.forge_kayk
                    pr.origin = pygame.Vector2(self.pos)
                    game.projectiles.append(pr)
            if self.divine_kayk:
                # +1 bala frontal e tres tiros curtos para tras/lados.
                for ang,life in ((base_a,1.2),(base_a+math.pi/2,0.48),(base_a-math.pi/2,0.48),(base_a+math.pi,0.48)):
                    d=vec_from_angle(ang)
                    pr=Projectile(self.pos+d*S(34),d*S(760),self.base_damage*0.72*self.projectile_bonus,"player",S(8),DIVINE_BLUE,life,self.projectile_pierce+self.kayk_soul_pierce)
                    pr.kind="dual_pistol"; pr.origin=pygame.Vector2(self.pos); game.projectiles.append(pr)
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
                base = math.atan2(self.facing.y, self.facing.x)
                count = 1 + self.pedro_extra_boomerangs
                for i in range(count):
                    spread = (i-(count-1)/2) * 0.22
                    shots.append(vec_from_angle(base+spread))
            for d in shots:
                boom = BoomerangProjectile(
                    self, d, self.base_damage*self.projectile_bonus,
                    self.pedro_speed_mult, self.pedro_range_mult,
                    self.pedro_return_hit, self.pedro_explosive, self.pedro_crown,
                )
                if self.forge_pedro:
                    boom.radius = int(boom.radius * 1.50)
                boom.divine_pedro = self.divine_pedro
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
            self.invuln = max(self.invuln, 0.15)
            AUDIO.play("dash", 0.72, 80)
            return

        # Pai do Kayk: golpe circular grande ao redor dele.
        if self.character == "Pai do Kayk":
            if not self.spend_stamina(10):
                return
            self.attack_cd = 0.82
            radius = S(270) * self.father_radius_mult
            game.father_wave_fx_timer = 0.48
            game.father_wave_fx_total = 0.48
            game.father_wave_fx_center = pygame.Vector2(self.pos)
            game.father_wave_fx_radius = radius
            hit_any = False
            old = game.current_damage_kind
            game.current_damage_kind = "father_wave"
            for e in list(game.enemies):
                if not e.dead and e.pos.distance_to(self.pos) <= radius + e.radius:
                    dmg = self.base_damage * self.effective_damage_mult(game, e, "father_wave", e.pos.distance_to(self.pos))
                    e.damage(dmg, game, self.pos)
                    hit_any = True
            maho=getattr(game,"mahoraga",None)
            if maho is not None and not maho.dead and maho.pos.distance_to(self.pos) <= radius+maho.radius:
                dmg=self.base_damage*self.effective_damage_mult(game,None,"father_wave",maho.pos.distance_to(self.pos))
                maho.take_damage(dmg,game,self.pos,from_player=True)
                hit_any=True
            game.current_damage_kind = old
            if self.father_clear_projectiles:
                game.projectiles = [pr for pr in game.projectiles if not (pr.owner == "enemy" and pr.pos.distance_to(self.pos) <= radius)]
            game.spawn_particles(self.pos, WHITE, 24)
            game.shake = max(game.shake, S(13))
            AUDIO.play("boss", 0.48, 180)
            if hit_any:
                game.register_combo_hit()
            return

        # Ycaro: shotgun.
        if self.character == "Ycaro":
            if not self.divine_ycaro and not self.spend_stamina(7):
                return
            self.attack_cd = (0.018 if ycaro_domain else 0.29) if self.divine_ycaro else (0.035 if ycaro_domain else 0.58)
            if self.divine_ycaro:
                self.speed_buff=max(self.speed_buff,0.85)
            base_a = math.atan2(self.facing.y, self.facing.x)
            pellets = 5 + self.ycaro_extra_pellets
            if ycaro_domain and self.domain_evolution:
                pellets += 1
            if ycaro_domain and self.ycaro_no_too_close:
                pellets += 2
            spread = 0.26 if self.ycaro_sawed_off else 0.20
            offsets = [0] if pellets == 1 else [(-spread + (2*spread)*i/(pellets-1)) for i in range(pellets)]
            for off in offsets:
                d = vec_from_angle(base_a + off)
                pr = Projectile(self.pos + d*S(35), d*S(690)*self.ycaro_pellet_speed,
                                self.base_damage*0.56*self.projectile_bonus, "player", S(7), ORANGE,
                                0.82*self.ycaro_pellet_speed, self.projectile_pierce)
                pr.kind = "shotgun"
                pr.origin = pygame.Vector2(self.pos)
                game.projectiles.append(pr)
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
        if not self.spend_stamina(dash_cost):
            return
        if move_dir.length_squared() == 0:
            move_dir = pygame.Vector2(self.facing)
        self.dash_dir = move_dir.normalize()
        special_dash = self.ana_vector_step or (self.character == "Kayk" and self.kayk_spectral_step)
        self.dash_time = 0.24 if special_dash else 0.18
        dash_cd_base = 0.50 if special_dash else 0.72
        self.dash_cd = dash_cd_base * max(0.60, 1.0 - 0.04 * SAVE.get("dash_level", 0))
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
            game.add_domain_charge(5)
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
        if self.character == "Potential Man":
            if game.domain_charge < 100:
                return
            alive=[x for x in game.potential_summons if isinstance(x,MahoragaSummon) and not x.dead]
            if alive:
                return
            game.domain_charge=0
            spawn=self.pos + (self.facing.normalize() if self.facing.length_squared() else pygame.Vector2(1,0))*S(130)
            maho=MahoragaSummon(spawn,self,game.wave)
            game.potential_summons.append(maho)
            game.mahoraga=maho
            game.mahoraga_hostile_to_dogs=False
            game.domain_name="MAHORAGA"
            game.domain_message_timer=1.8
            game.damage_texts.append(DamageText("MAHORAGA INVOCADO",pygame.Vector2(self.pos),YELLOW,1.1))
            AUDIO.play("domain",1.0,250)
            game.shake=max(game.shake,S(18))
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
            game.domain_duration=10.0
            game.domain_timer=10.0
            game.domain_name="BAD TIME"
            game.domain_message_timer=1.8
            game.bad_time_bone_cd=0.05
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
        # V11: o Dominio nasce FIXO neste ponto e sua area base e 50% maior.
        base_radius = S(375)
        if self.character == "Pai do Kayk":
            base_radius *= self.father_domain_radius_mult
        game.domain_radius = base_radius
        game.domain_duration = 8.0 + (2.0 if self.domain_evolution else 0.0)
        if self.character == "Pai do Kayk":
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

        # Ruan: invoca um guardiao-BOSS que existe ate o fim da Expansao.
        if self.character == "Ruan":
            self.heal(self.max_hp * 0.28, game)
            self.recover_stamina(self.max_stamina * 0.45, game)
            guardian = RuanServant(self.pos + pygame.Vector2(S(70), 0), self, self, guardian=True)
            game.servants.append(guardian)
            game.ruan_guardian = guardian
            game.damage_texts.append(DamageText("GUARDIAO INVOCADO!", pygame.Vector2(self.pos), CYAN, 1.1))

        # Pai do Kayk jogavel: tudo que estiver DENTRO da area e sentenciado na hora.
        if self.character == "Pai do Kayk":
            old = game.current_damage_kind
            game.current_damage_kind = "father_domain"
            for e in list(game.enemies):
                if not e.dead and game.is_in_domain(e.pos):
                    e.hp = 0
                    e.die(game)
            game.current_damage_kind = old
            if self.father_domain_refill:
                self.hp = self.max_hp
                self.stamina = self.max_stamina
            game.damage_texts.append(DamageText("SENTENCA ABSOLUTA", pygame.Vector2(self.pos), WHITE, 1.1))

        # Se um boss ja abriu seu Dominio e os circulos se encontram, comeca o choque.
        for e in game.enemies:
            if isinstance(e, Boss) and not e.dead and e.domain_active and game.domains_overlap(e):
                game.start_domain_clash(e)
                break

    def update(self, dt, game, move_dir):
        self.attack_cd = max(0, self.attack_cd - dt)
        self.dash_cd = max(0, self.dash_cd - dt)
        self.parry_cd = max(0, self.parry_cd - dt)
        self.parry_time = max(0, self.parry_time - dt)
        self.invuln = max(0, self.invuln - dt)
        self.speed_buff = max(0, self.speed_buff - dt)
        self.predator_timer = max(0, self.predator_timer - dt)
        self.ana_forge_cd = max(0.0, getattr(self, "ana_forge_cd", 0.0)-dt)
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
        if self.overclock and self.stamina >= self.max_stamina * 0.80:
            speed_mult *= 1.20
        if self.no_brakes:
            speed_mult *= 1.40
        if self.god_not_watching and self.hp <= self.max_hp * 0.20:
            speed_mult *= 1.55
        if self.character == "Kevyn" and self.in_domain(game):
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
        if self.stamina_regen_delay <= 0 and self.dash_time <= 0 and self.ruan_attack_time <= 0:
            cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
            self.stamina = min(cap, self.stamina + regen * dt)
        if self.character == "Sans" and self.sans_exhausted:
            # Abaixo de 15% ele continua EXAUSTO: anda devagar, mas ataque/Dash/Blaster ficam bloqueados.
            if self.stamina >= self.max_stamina*0.15:
                self.sans_exhausted=False
                game.damage_texts.append(DamageText("RECUPERADO",pygame.Vector2(self.pos),CYAN,0.8))

        # Kevyn agora regenera passivamente 2 HP por segundo.
        if self.character == "Kevyn" and self.hp > 0:
            self.hp = min(self.max_hp, self.hp + 2.0 * dt)

        # Ruan se regenera continuamente enquanto permanece na propria Expansao.
        if self.character == "Ruan" and self.in_domain(game):
            hp_rate = 0.055 if self.ruan_king_dead else 0.032
            sta_rate = 0.22 if self.ruan_king_dead else 0.13
            self.hp = min(self.max_hp, self.hp + self.max_hp * hp_rate * dt)
            cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
            self.stamina = min(cap, self.stamina + self.max_stamina * sta_rate * dt)

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
            if self.forge_ruan and random.random() < 0.55:
                game.forge_fire_trails.append(ForgeFireTrail(self.pos, max(2.0, self.base_damage*0.22)))
            game.spawn_particles(self.pos, CYAN, 1)
        elif self.dash_time > 0:
            self.dash_time -= dt
            dash_base = min(self.base_speed, S(560))
            self.pos += self.dash_dir * dash_base * (3.7 if (self.ana_vector_step or (self.character == "Kayk" and self.kayk_spectral_step)) else 3.2) * dt
            if self.forge_ruan and random.random() < 0.55:
                game.forge_fire_trails.append(ForgeFireTrail(self.pos, max(2.0, self.base_damage*0.18)))
            game.spawn_particles(self.pos, CYAN, 1)
        elif move_dir.length_squared() > 0:
            d = move_dir.normalize()
            self.facing = d
            walk_speed = min(self.base_speed * self.speed_mult, S(700))
            self.pos += d * walk_speed * dt

        self.pos.x = clamp(self.pos.x, self.radius, W - self.radius)
        self.pos.y = clamp(self.pos.y, S(205) + self.radius, H - S(335) - self.radius)

    def draw(self, offset, game):
        p = self.pos + offset
        color = self.color if self.invuln <= 0 else WHITE
        pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius)
        if self.character == "Potential Man":
            pygame.draw.circle(SCREEN, WHITE, (int(p.x), int(p.y)), self.radius, max(2,S(5)))
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
            d = self.facing if self.facing.length_squared() > 0 else pygame.Vector2(1,0)
            end = p + d.normalize()*S(78)
            pygame.draw.line(SCREEN, GREEN, p, end, max(S(8),S(12)))
            pygame.draw.circle(SCREEN, WHITE, (int(end.x),int(end.y)), S(8), max(1,S(2)))
        if game.slash_fx > 0 and self.weapon == 0:
            a = math.atan2(self.facing.y, self.facing.x)
            r = S(105) * self.kevyn_sword_range
            rect = pygame.Rect(p.x-r, p.y-r, r*2, r*2)
            pygame.draw.arc(SCREEN, WHITE, rect, -(a+0.8), -(a-0.8), S(9))


class Game:
    def __init__(self):
        self.state = "menu"
        self.mode = "arena"  # "arena" ou "afk"
        self.selected_character = "Ycaro"
        self.selection_target = "arena"
        self.difficulty = "easy"
        self.pending_character = None
        self.difficulty_rects = []
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
        self.domain_active = False
        self.domain_timer = 0.0
        self.domain_duration = 8.0
        self.domain_center = pygame.Vector2(W/2, H/2)
        self.domain_radius = S(375)
        # V8: sem cutscene/overlay de dominio. Apenas mensagem curta + efeito.
        self.domain_cutscene_timer = 0.0
        self.domain_cutscene_total = 0.0
        self.domain_pending = False
        self.domain_name = ""
        self.domain_message_timer = 0.0
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
        self.buttons = self.make_buttons()
        self.afk_buttons = self.make_afk_buttons()
        self.wave_banner = 0
        self.wave_clear_lock = False
        self.owned_upgrades = set()
        self.owned_upgrade_counts = {}
        self.synergies = set()
        self.catalog_page = 0
        self.bestiary_page = 0
        self.run_upgrade_page = 0
        self.shop_page = 0
        self.forge_page = 0
        self.forge_character_index = 0
        self.items_page = 0
        self.items_tab = "materials"
        self.whats_new_scroll = 0.0
        self.whats_new_drag_start = None
        self.whats_new_scroll_start = 0.0
        self.whats_new_max_scroll = 0.0
        self.whats_new_overscroll = S(95)
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
        self.bad_time_bone_cd = 0.0
        self.bad_time_obstacle_cd = 0.0
        self.sans_bones = []
        self.sans_blaster_fx = []
        self.mass_hit_fx = False
        # Potential Man / shikigamis
        self.potential_summons = []
        self.mahoraga = None
        self.mahoraga_hostile_to_dogs = False
        self.vinicius_turrets=[]; self.vinicius_walls=[]; self.vinicius_rocks=[]
        self.vinicius_scrap=0; self.vinicius_mini_kills=0; self.vinicius_mega_pending=False; self.vinicius_mega_choice_rects=[]
        self.training_target_name=None; self.training_respawn_timer=0.0; self.bestiary_train_rects=[]
        self.sync_saved_achievements()

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
        self.__init__()
        self.selected_character = chosen
        self.difficulty = chosen_difficulty if chosen_difficulty in DIFFICULTIES else "easy"
        self.state = "playing"
        self.mode = "arena"
        self.player = Player(self, chosen)
        self.start_ticks = pygame.time.get_ticks()
        self.add_mission_progress("runs", 1)
        if SAVE.get("cheat_dev", False):
            self.wave = max(1, int(SAVE.get("cheat_start_wave", 1) or 1))
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
        if name == "Pai do Kayk":
            return SAVE.get("father_unlocked", False)
        if name == "Sans":
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
        pos=(W*0.68,H*0.48); e=None; normal={"PERSEGUIDOR":"chaser","ATIRADOR":"shooter","KITER":"kiter","TANQUE":"tank"}; elites={"ELITE: FRENESI":"frenzy","ELITE: GIGANTE":"giant","ELITE: BLINDADO":"armored","ELITE: EXPLOSIVO":"explosive"}; boss_waves={"PAI DO KAYK":5,"O DEVORADOR":10,"A SENTINELA":15,"REI DO VAZIO":20}
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
        if not recipe or recipe.get("preview",False):
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
        if not recipe or recipe.get("preview",False) or key not in set(SAVE.get("crafted_weapons",[])): return False
        SAVE.setdefault("equipped_weapons",{})[recipe["character"]]=key
        save_data(SAVE); AUDIO.play("upgrade",0.75)
        self.unlock_notice=f"EQUIPADO: {recipe['name']}"; self.unlock_notice_timer=2.5
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

    def spawn_wave(self):
        self.update_mission_wave()
        self.wave_banner = 1.7
        self.wave_clear_lock = False
        self.choose_event()
        special_sin = sin_encounter_for_wave(self.wave)
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
        elif self.wave % 5 == 0:
            boss = Boss((W/2, S(350)), self.wave)
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
            count = min(max(1,int((4 + cw * 2) * dcfg["count"])), count_cap)
            kinds = ["chaser", "shooter"]
            if cw >= 2:
                kinds.append("kiter")
            if cw >= 3:
                kinds.append("tank")
            elite_cap = min(0.94, (0.72 if cw >= 150 else 0.52 if cw >= 75 else 0.37) + dcfg["elite"])
            elite_chance = min(0.08 + cw * 0.015 + dcfg["elite"], elite_cap)
            for _ in range(count):
                kind = random.choice(kinds)
                elite = None
                if random.random() < elite_chance:
                    elite = random.choice(["frenzy", "giant", "armored", "explosive"])
                e = Enemy(self.random_spawn_pos(), kind, self.wave, elite)
                e.speed *= self.enemy_speed_mult * self.enemy_perma_speed_mult
                e.contact_damage *= self.enemy_damage_mult
                self.enemies.append(e)

        # Aplica o preset por ultimo, preservando os multiplicadores/eventos antigos do FACIL.
        for enemy in self.enemies:
            self.apply_difficulty_to_enemy(enemy)

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
        self.run_rewards_banked = True
        save_data(SAVE)
        return True

    def leave_run_to_menu(self):
        """Saida voluntaria: guarda o que foi conquistado antes de abandonar a run."""
        self.bank_run_rewards()
        self.attack_held = False; self.parry_held=False; self.domain_held=False; self.dash_held=False
        for key in self.move_touch:
            self.move_touch[key] = False
        self.active_fingers.clear()
        self.joystick_finger = None
        self.joystick_mouse_active = False
        self.joystick_vector.update(0, 0)
        self.state = "menu"

    def end_run(self):
        if self.player.character == "Glonk":
            self.bank_run_rewards()
            AUDIO.play("glonk", 1.0)
            self.state = "glonk_death"
            self.attack_held = False; self.parry_held=False; self.domain_held=False; self.dash_held=False
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
        # Garante que nenhum dos dois dominios expire no meio do choque.
        self.domain_timer = max(self.domain_timer, 5.25)
        boss.domain_timer = max(boss.domain_timer, 5.25)
        self.clash_result = "CHOQUE DE DOMINIOS"
        self.clash_result_timer = 1.8
        AUDIO.play("domain", 1.0, 250)
        self.shake = max(self.shake, S(16))

    def record_clash_damage(self, amount):
        if self.domain_clash_active:
            self.domain_clash_score += max(0.2, amount * 0.12)

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
            self.bad_time_bone_cd=0.30
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
        # Se os circulos se separarem, o choque ainda continua: os Dominios ja se enfrentaram.
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

    def update_mission_wave(self):
        if self.mode != "arena" or is_beta_character(self.player.character):
            return
        char = self.player.character
        stats = self.mission_stats_for(char)
        if self.wave > stats.get("best_wave", 0):
            stats["best_wave"] = self.wave
            self.check_character_missions(char)
        if self.wave >= 50:
            self.unlock_achievement("wave_50")
        if self.wave >= 100:
            self.unlock_achievement("wave_100")
        if self.wave >= 250:
            self.unlock_achievement("wave_250")
        if self.wave >= 500:
            self.unlock_achievement("wave_500")
        if self.wave >= 700:
            self.unlock_achievement("wave_700")
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

    def add_domain_charge(self, amount):
        mult = (2.0 if self.player.devil_pact else 1.0) * (1.0 + 0.06 * SAVE.get("domain_level", 0))
        if self.player_in_boss_domain("void"):
            mult *= 0.30
        self.domain_charge = clamp(self.domain_charge + amount * mult, 0, 100)

    def is_in_domain(self, pos):
        return self.domain_active and pygame.Vector2(pos).distance_to(self.domain_center) <= self.domain_radius

    def register_combo_hit(self):
        self.combo = min(50, self.combo + 1)
        self.combo_timer = 3.0
        if self.combo >= 50:
            self.unlock_achievement("combo_50")
        if self.player.vampire_heart and self.combo > 0 and self.combo % 8 == 0:
            self.player.heal(max(2, self.player.max_hp * 0.025), self)

    def on_enemy_killed(self, enemy):
        self.add_domain_charge(8)
        p = self.player
        if p.character == "Vinicius 13" and self.mode == "arena":
            self.vinicius_scrap = min(20, self.vinicius_scrap + 1); self.vinicius_mini_kills += 1
            if self.vinicius_mini_kills >= 5:
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
        if p.character == "Pai do Kayk" and p.father_boss_heal and isinstance(enemy, Boss):
            p.heal(p.max_hp * 0.30, self)
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
        kind=random.choice(["heal","random","shot","wall"]); pos=self.player.pos+vec_from_angle(random.random()*math.tau)*S(95); pos.x=clamp(pos.x,S(70),W-S(70)); pos.y=clamp(pos.y,S(220),H-S(390)); self.vinicius_turrets.append(ViniciusTurret(pos,kind,self.player,False)); self.damage_texts.append(DamageText("TORRE "+ViniciusTurret.LABELS[kind],pygame.Vector2(pos),YELLOW,0.9)); AUDIO.play("upgrade",0.55,80); return True

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
        pool = UNIVERSAL_UPGRADES + CHARACTER_UPGRADES.get(self.player.character, [])
        available = [
            c for c in pool
            if (c[3] in STACKABLE_UPGRADES or c[3] not in self.owned_upgrades)
            and not (c[3] == "quick_feet" and self.owned_upgrade_counts.get("quick_feet", 0) >= 6)
        ]
        weights = {"common": 46, "rare": 29, "epic": 15, "legendary": 7, "cursed": 3}
        cards = []
        for _ in range(min(n, len(available))):
            total = sum(weights[x[0]] for x in available)
            roll = random.uniform(0, total)
            acc = 0
            pick = available[-1]
            for x in available:
                acc += weights[x[0]]
                if roll <= acc:
                    pick = x
                    break
            cards.append(pick)
            available.remove(pick)
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
        # Pai do Kayk jogavel
        elif key == "father_wave": p.father_radius_mult *= 1.25
        elif key == "father_slap": p.father_damage_mult *= 1.30
        elif key == "father_lung": p.max_stamina += 30; p.recover_stamina(30)
        elif key == "father_authority": p.father_clear_projectiles = True
        elif key == "father_family_issues": p.father_boss_bonus = True
        elif key == "father_present": p.father_boss_heal = True
        elif key == "father_sentence_circle": p.father_domain_radius_mult *= 1.35; p.domain_evolution = True
        elif key == "father_final_word": p.father_domain_refill = True; p.domain_evolution = True

        AUDIO.play("upgrade", 0.90)
        self.check_synergies()
        self.state = "playing"
        self.mode = self.upgrade_return_mode
        if self.mode == "afk":
            if not any(isinstance(e, TrainingDummy) for e in self.enemies):
                self.spawn_training_dummy()
        else:
            self.wave += 1
            self.healing_locked = False
            self.spawn_wave()

    def check_synergies(self):
        combos = [
            ({"explosive_parry", "broken_time"}, "PARADOXO BALISTICO"),
            ({"ycaro_point_blank", "ycaro_more_pellets"}, "EXECUCAO BALISTICA"),
            ({"ana_impossible_shot", "ana_reality_error"}, "GEOMETRIA IMPOSSIVEL"),
            ({"kevyn_human_wall", "kevyn_time_counter"}, "FORTALEZA DO FIM"),
            ({"blood_debt", "last_breath"}, "PACTO DE SOBREVIVENCIA"),
            ({"pedro_round_trip", "pedro_explosive_pineapple"}, "COLHEITA DE GUERRA"),
            ({"ruan_brutal_charge", "ruan_fallen_pact"}, "MARCHA DOS AMIGOS"),
        ]
        for req, name in combos:
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

    def handle_touch_motion(self, pos, finger_id=None):
        if self.state != "playing":
            return
        if finger_id is not None:
            if self.joystick_finger == finger_id:
                self.update_joystick(pos)
        elif self.joystick_mouse_active:
            self.update_joystick(pos)

    def handle_touch_down(self, pos, finger_id=None):
        if self.state == "playing":
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
                self.attack_held = True
                if finger_id is not None: self.active_fingers[finger_id] = "attack"
                if self.player.character == "Potential Man":
                    self.player.potential_hold_timer=0.0; self.player.potential_hold_triggered=False
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
                else: self.player.expand_domain(self)

    def handle_touch_up(self, pos, finger_id=None):
        if finger_id is not None:
            action = self.active_fingers.pop(finger_id, None)
            if action in self.move_touch:
                self.move_touch[action] = False
            elif action == "joystick":
                if self.joystick_finger == finger_id:
                    self.joystick_finger = None
                    self.joystick_vector.update(0, 0)
            elif action == "attack":
                if self.player.character == "Potential Man" and not self.player.potential_hold_triggered: self.player.attack(self)
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
            if self.attack_held:
                if self.player.character == "Potential Man" and not self.player.potential_hold_triggered: self.player.attack(self)
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
        self.time += dt
        self.domain_message_timer = max(0, self.domain_message_timer - dt)
        self.boss_domain_message_timer = max(0, self.boss_domain_message_timer - dt)
        self.clash_result_timer = max(0, self.clash_result_timer - dt)
        self.unlock_notice_timer = max(0, self.unlock_notice_timer - dt)
        self.wave_banner = max(0, self.wave_banner - dt)
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
                # Guardiao do Ruan so existe enquanto o Dominio estiver ativo.
                if self.ruan_guardian is not None:
                    self.ruan_guardian.dead = True
                    self.ruan_guardian = None

        # Pequenas orbes de vida aparecem naturalmente pelo mapa.
        self.ambient_heal_orb_timer -= dt
        if self.ambient_heal_orb_timer <= 0:
            if sum(1 for d in self.drops if d.kind == "ambient_heal") < 4:
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
                targets = [e for e in self.enemies if not e.dead and self.is_in_domain(e.pos)]
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
        if self.attack_held and self.player.character not in ("Sans", "Potential Man") and not self.player.has_divine_attack_hold():
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

        # Dominios sao moveis: se os circulos se encostarem DEPOIS de ativados,
        # o Choque ainda comeca. Nao depende apenas do instante da ativacao.
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

        new_projectiles = []
        for pr in self.projectiles:
            # Tempo de Caca: abacaxi teleguiado durante a ida.
            if isinstance(pr,BoomerangProjectile) and getattr(pr,"divine_pedro",False) and not pr.returning:
                targets=[e for e in self.enemies if not e.dead and e.id not in pr.hit_ids]
                if targets:
                    target=min(targets,key=lambda e:e.pos.distance_to(pr.pos)); desired=target.pos-pr.pos
                    if desired.length_squared()>0: pr.vel=pr.vel.lerp(desired.normalize()*pr.base_speed,min(1.0,7.5*dt))
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
            # Metavisao do Cadeado Azul: projeteis inimigos perdem muita velocidade dentro da area.
            if (pr.owner == "enemy" and self.player.character == "Strikada Egoísta" and self.domain_active
                    and self.is_in_domain(pr.pos)):
                proj_mult *= 0.45
            proj_dt = dt * proj_mult
            if not pr.update(proj_dt):
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

            if pr.owner == "enemy":
                if self.player.parry_time > 0 and pr.pos.distance_to(self.player.pos) <= S(95):
                    pr.owner = "player"
                    pr.vel *= -1.35
                    pr.damage *= 2.2
                    pr.color = YELLOW
                    pr.parry_reflected = True
                    self.player.recover_stamina(10, self)
                    self.parries += 1
                    self.add_domain_charge(7)
                    self.record_clash_parry()
                    AUDIO.play("parry", 0.95, 80)
                    self.damage_texts.append(DamageText("PARRY!", pygame.Vector2(self.player.pos), YELLOW))
                    self.shake = max(self.shake, S(9))
                    if "PARADOXO BALISTICO" in self.synergies:
                        self.enemy_slow_timer = max(self.enemy_slow_timer, 1.25)
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
                        if random.random() < self.player.crit_chance:
                            dmg *= 2
                        maho.take_damage(dmg, self, pr.pos, from_player=True)
                        pr.hit_mahoraga = True
                        self.player.recover_stamina(self.player.stamina_on_hit, self)
                        self.register_combo_hit()
                        if not isinstance(pr, BoomerangProjectile):
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
                        if isinstance(pr, BoomerangProjectile) and pr.returning and pr.crown:
                            dmg *= 1.65
                            self.damage_texts.append(DamageText("COROA!", pygame.Vector2(e.pos), YELLOW))
                        if random.random() < self.player.crit_chance:
                            dmg *= 2
                            self.damage_texts.append(DamageText("CRIT!", pygame.Vector2(e.pos), YELLOW))
                        self.current_damage_kind = source
                        was_alive_before_hit = not e.dead
                        e.damage(dmg, self, pr.pos)
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
                        double_chance = getattr(pr, "double_hit_chance", 0.0)
                        if self.player.character == "Ana" and self.domain_active and self.is_in_domain(e.pos) and self.player.domain_evolution:
                            double_chance = max(double_chance, 0.25)
                        if self.player.character == "Ana" and self.player.ana_reality_exe and self.domain_active and self.is_in_domain(e.pos):
                            double_chance = max(double_chance, 0.45)
                        if random.random() < double_chance:
                            e.damage(dmg, self, pr.pos)
                            self.damage_texts.append(DamageText("ERRO x2", pygame.Vector2(e.pos), PINK))
                        self.current_damage_kind = None
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
                                    child=Projectile(e.pos+d.normalize()*S(18),d.normalize()*S(690),pr.damage*0.72,"player",S(7),RED,1.55,0); child.kind="vinicius_bolt"; child.origin=pygame.Vector2(e.pos); child.vinicius_child=True; child.hit_ids.add(e.id); new_projectiles.append(child)

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
                            infinite = self.domain_active and self.player.character == "Strikada Egoísta" and self.is_in_domain(e.pos)
                            if not infinite:
                                pr.strikada_hits_left = max(0, getattr(pr, "strikada_hits_left", 4)-1)
                            # Quando todos os alvos ja foram tocados no Dominio, libera uma nova volta.
                            options = [o for o in self.enemies if not o.dead and o.id not in pr.hit_ids and o is not e]
                            if infinite and not options:
                                pr.hit_ids = {e.id}
                                options = [o for o in self.enemies if not o.dead and o is not e]
                            can_continue = infinite or getattr(pr, "strikada_hits_left", 0) > 0
                            if can_continue and options:
                                target = min(options, key=lambda o:o.pos.distance_to(e.pos))
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
                                    rp.double_hit_chance=getattr(pr,"double_hit_chance",0.0)
                                    new_projectiles.append(rp)

                        if isinstance(pr, BoomerangProjectile):
                            # O bumerangue continua seu caminho e depois retorna.
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
            if dist <= d.radius + self.player.radius + S(8):
                if str(d.kind).startswith("mat:"):
                    self.collect_forge_material(d.kind.split(":",1)[1],1)
                    continue
                if d.kind == "heal":
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
                    self.run_coins += max(1,int(8 * self.coin_multiplier * reward_mult))
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
        elif not self.enemies and not self.wave_clear_lock and self.state == "playing":
            self.wave_clear_lock = True
            if self.mahoraga is not None and not self.mahoraga.dead:
                self.mahoraga.end_wave_adapt(self)
            self.player.heal(10, self)
            self.player.recover_stamina(18, self)
            AUDIO.play("wave_clear", 0.85)
            self.roll_evolution_point()
            self.open_upgrade()

    def update(self, dt):
        self.evolution_notice_timer = max(0.0, self.evolution_notice_timer - dt)
        if self.state == "playing":
            self.update_playing(dt)
        elif self.state in ("menu", "character_select", "difficulty_select", "shop", "upgrade", "death", "glonk_death", "upgrade_catalog", "bestiary", "forge", "items", "weapons", "control_editor", "run_upgrades", "whats_new", "achievements", "missions", "cheats", "vinicius_mega"):
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

        draw_text(f"{p.character} | {p.weapon_name}", FONT_S, p.color, (x, sy+S(48)))
        if self.mode == "afk":
            draw_text("ZONA AFK", FONT_M, CYAN, (x, sy+S(82)))
        elif self.mode == "training":
            draw_text("TREINO: "+str(self.training_target_name), FONT_M, CYAN, (x, sy+S(82)))
        else:
            draw_text(f"ONDA {self.wave}", FONT_M, WHITE, (x, sy+S(82)))
            dcfg = difficulty_cfg(getattr(self,"difficulty","easy"))
            draw_text(dcfg["name"], FONT_S, dcfg["color"], (x+S(245), sy+S(92)))
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
        elif p.character=="Vinicius 13":
            minis=sum(1 for t in self.vinicius_turrets if not t.dead and not t.mega); megas=[t for t in self.vinicius_turrets if t.mega and not t.dead]
            if megas:
                mt=megas[0]; special_text=f"SUCATA {self.vinicius_scrap}/20 | MINI {minis}/5 | {ViniciusTurret.LABELS.get(mt.kind,'MEGA')} {_cd(mt.cd)}"
            else:
                special_text=f"SUCATA {self.vinicius_scrap}/20 | MINI {minis}/5 | MEGA AGUARDANDO"
        if special_text:
            draw_text(special_text,FONT_S,special_color,(cool_x,cool_y+S(30)))

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

        circle_button(self.buttons["attack"], "ATK", RED)
        circle_button(self.buttons["dash"], "DASH", CYAN)
        if self.player.character == "Sans":
            blast_color = CYAN if self.player.sans_blaster_cd <= 0 and not self.player.sans_exhausted else PANEL2
            circle_button(self.buttons["parry"], "BLAST", blast_color)
        else:
            circle_button(self.buttons["parry"], "PARRY", YELLOW)
        sans_ready = self.player.character == "Sans" and (self.domain_charge >= 100 or self.player.stamina < self.player.max_stamina*0.50) and not self.player.sans_exhausted
        dom_color = PURPLE if ((self.domain_charge >= 100 and self.player.character not in ("Glonk", "Glonk 100% Power", "Vinicius 13")) or sans_ready) else PANEL2
        dom_label = "BAD" if self.player.character == "Sans" else ("MAHO" if self.player.character == "Potential Man" else ("AUTO" if self.player.character=="Vinicius 13" else "DOM"))
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

    def draw_playing(self):
        self.draw_bg()
        offset = self.camera_offset()
        self.draw_domain_zone(offset)
        self.draw_father_wave_fx(offset)
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
        self.draw_controls()

        if self.wave_banner > 0 and self.mode == "arena":
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
            draw_text("CHOQUE DE DOMINIOS", FONT_L, YELLOW, (W/2, H*0.49), True)
            draw_text(f"{self.domain_clash_timer:.1f}s   PODER {self.domain_clash_score:+.1f}", FONT_M, WHITE, (W/2, H*0.545), True)
        elif self.clash_result_timer > 0:
            draw_text(self.clash_result, FONT_M, YELLOW if "SOBERANO" in self.clash_result else RED, (W/2, H*0.49), True)
        if self.flash_screen > 0:
            surf = pygame.Surface((W,H), pygame.SRCALPHA)
            surf.fill((255,255,255,int(160*self.flash_screen/0.22)))
            SCREEN.blit(surf,(0,0))
        self.draw_domain_cutscene()

    def draw_menu(self):
        SCREEN.fill(BG)
        title = "Derrote o Gordo do Pai do Kayk"
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
        upgrades = pygame.Rect(right_x, rows[0], bw, bh)
        bestiary = pygame.Rect(right_x, rows[1], bw, bh)
        controls = pygame.Rect(right_x, rows[2], bw, bh)
        for rect, color, label in [
            (start, RED, "JOGAR"), (afk, CYAN, "ZONA AFK / TESTES"), (shop, PANEL2, "LOJA PERMANENTE"),
            (upgrades, PURPLE, "TODOS OS UPGRADES"), (bestiary, ORANGE, "BESTIARIO"), (controls, BLUE, "EDITAR CONTROLES"),
        ]:
            pygame.draw.rect(SCREEN, color, rect, border_radius=S(22))
            draw_text(label, FONT_M if label == "JOGAR" else FONT_S, DARK if color in (CYAN, ORANGE) else WHITE, rect.center, True)

        aw, ah, ag = S(300), S(62), S(24)
        sfx_btn = pygame.Rect(W/2-aw-ag//2, int(H*0.68), aw, ah)
        music_btn = pygame.Rect(W/2+ag//2, int(H*0.68), aw, ah)
        pygame.draw.rect(SCREEN, GREEN if AUDIO.sfx_on else PANEL2, sfx_btn, border_radius=S(16))
        pygame.draw.rect(SCREEN, GREEN if AUDIO.music_on else PANEL2, music_btn, border_radius=S(16))
        draw_text("EFEITOS: " + ("ON" if AUDIO.sfx_on else "OFF"), FONT_S, DARK if AUDIO.sfx_on else WHITE, sfx_btn.center, True)
        draw_text("MUSICA: " + ("ON" if AUDIO.music_on else "OFF"), FONT_S, DARK if AUDIO.music_on else WHITE, music_btn.center, True)
        self.menu_sfx_rect = sfx_btn
        self.menu_music_rect = music_btn

        # Abas compactas extras. Novidades fica no canto inferior esquerdo, Conquistas logo acima.
        tab_w, tab_h = S(270), S(46)
        bottom_tab_y = H - CONTROL_SAFE_Y - tab_h - S(6)
        news = pygame.Rect(CONTROL_SAFE_X, bottom_tab_y, tab_w, tab_h)
        ach = pygame.Rect(CONTROL_SAFE_X, bottom_tab_y-tab_h-S(8), tab_w, tab_h)
        missions = pygame.Rect(W-CONTROL_SAFE_X-tab_w, bottom_tab_y-tab_h-S(8), tab_w, tab_h)
        cheats = pygame.Rect(W-CONTROL_SAFE_X-tab_w, bottom_tab_y, tab_w, tab_h)
        for r,label,color in [(news,"NOVIDADES",CYAN),(ach,"CONQUISTAS",YELLOW),(missions,"MISSOES",PURPLE),(cheats,"CHEATS",RED)]:
            pygame.draw.rect(SCREEN,color,r,border_radius=S(12)); draw_text(label,FONT_S,DARK if color in (CYAN,YELLOW) else WHITE,r.center,True)
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
        if SAVE.get("father_unlocked", False):
            draw_text("PAI DO KAYK DESBLOQUEADO", FONT_S, WHITE, (W/2, H*0.85), True)
        elif SAVE.get("kayk_unlocked", False):
            draw_text(f"KAYK DESBLOQUEADO   |   PROGRESSO PAI DO KAYK: {progress}/{len(FATHER_UNLOCK_CHARACTERS)}", FONT_S, PURPLE, (W/2, H*0.85), True)
        else:
            draw_text("Derrote o Pai do Kayk para desbloquear Kayk", FONT_S, PURPLE, (W/2, H*0.85), True)
        draw_text("JOYSTICK | ATK | DASH | PARRY | DOM | PAUSE", FONT_S, GRAY, (W/2, H-CONTROL_SAFE_Y-S(4)), True)

        self.menu_start_rect = start
        self.menu_afk_rect = afk
        self.menu_shop_rect = shop
        self.menu_upgrades_rect = upgrades
        self.menu_bestiary_rect = bestiary
        self.menu_controls_rect = controls

    def draw_character_select(self):
        SCREEN.fill(BG)
        mode_text = "PARTIDA" if self.selection_target == "arena" else "ZONA AFK"
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
            draw_text(name.upper(), FONT_M if center_slot else FONT_S, color, (r.centerx, r.y+S(38)), True)
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
        detail = pygame.Rect(int(W*0.52), S(205), int(W*0.45)-CONTROL_SAFE_X, H-S(290))
        pygame.draw.rect(SCREEN, PANEL, detail, border_radius=S(22))
        pygame.draw.rect(SCREEN, cfg["color"], detail, width=max(2,S(4)), border_radius=S(22))
        draw_text(f"{selected.upper()}  |  " + ("BETA" if beta_selected else f"NIVEL {evolution_level(selected)}"), FONT_M, cfg["color"], (detail.x+S(22),detail.y+S(22)))
        if beta_selected:
            draw_text("PROGRESSAO DESATIVADA", FONT_S, CYAN, (detail.x+S(22),detail.y+S(70)))
            draw_text("Beta nao ganha pontos, moedas, recordes, missoes ou conquistas.", FONT_S, GRAY, (detail.x+S(22),detail.y+S(103)))
        else:
            draw_text(f"PONTOS DISPONIVEIS: {prof.get('points',0)}", FONT_S, YELLOW, (detail.x+S(22),detail.y+S(70)))
            draw_text("Ponto por onda: 100% GARANTIDO (+1 por onda vencida)", FONT_S, GREEN, (detail.x+S(22),detail.y+S(103)))

        # Valores reais com upgrades permanentes + evolucao aplicados, para a ficha ser precisa.
        actual_damage = cfg["damage"] * (1 + 0.08 * SAVE.get("damage_level",0)) * (1 + 0.03 * prof.get("strength",0))
        actual_speed = cfg["speed"] * (1 + 0.03 * SAVE.get("speed_level",0)) * (1 + 0.015 * prof.get("speed",0))
        actual_hp = 1 if selected in ("Sans", "Glonk 100% Power") else cfg["hp"] + SAVE.get("vitality_level",0)*8 + prof.get("hp",0)*6
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

        row_y = detail.y + S(205)
        row_h = max(S(60), int((detail.h-S(290))/6))
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
        play = pygame.Rect(detail.x, H-CONTROL_SAFE_Y-S(58), detail.w, S(58))
        pygame.draw.rect(SCREEN, cfg["color"] if unlocked else PANEL2, play, border_radius=S(15))
        launch = "ENTRAR NA ZONA AFK" if self.selection_target == "afk" else "JOGAR COM ESTE PERSONAGEM"
        draw_text(launch if unlocked else "PERSONAGEM BLOQUEADO", FONT_S, DARK if unlocked else GRAY, play.center, True)
        self.character_play_rect = play

    def all_upgrade_entries(self):
        out = [("UNIVERSAL", card) for card in UNIVERSAL_UPGRADES]
        for char, cards in CHARACTER_UPGRADES.items():
            for card in cards:
                out.append((char.upper(), card))
        return out

    def draw_upgrade_catalog(self):
        SCREEN.fill(BG)
        draw_text("CATALOGO DE UPGRADES", FONT_L, WHITE, (W/2, S(58)), True)
        entries = self.all_upgrade_entries()
        per_page = 6
        pages = max(1, math.ceil(len(entries)/per_page))
        self.catalog_page = int(clamp(self.catalog_page, 0, pages-1))
        start = self.catalog_page*per_page
        subset = entries[start:start+per_page]
        rarity_color = {"common":GRAY, "rare":BLUE, "epic":PURPLE, "legendary":YELLOW, "cursed":RED}
        rarity_name = {"common":"COMUM", "rare":"RARO", "epic":"EPICO", "legendary":"LENDARIO", "cursed":"AMALDICOADO"}
        cols = 2
        gap = S(22)
        top = S(135)
        card_w = int((W-SAFE*2-gap)/2)
        card_h = S(230)
        for i, (source, card) in enumerate(subset):
            rarity, name, desc, key = card
            col, row = i%cols, i//cols
            r = pygame.Rect(SAFE+col*(card_w+gap), top+row*(card_h+gap), card_w, card_h)
            pygame.draw.rect(SCREEN, PANEL, r, border_radius=S(18))
            pygame.draw.rect(SCREEN, rarity_color[rarity], r, width=max(2,S(4)), border_radius=S(18))
            draw_text(f"{source} | {rarity_name[rarity]}", FONT_S, rarity_color[rarity], (r.x+S(18), r.y+S(14)))
            draw_text(name, FONT_M, WHITE, (r.x+S(18), r.y+S(58)))
            draw_wrapped_text(desc, FONT_S, GRAY, pygame.Rect(r.x+S(18), r.y+S(112), r.w-S(36), S(86)), 3, False, 3)
        draw_text(f"PAGINA {self.catalog_page+1}/{pages}   |   {len(entries)} UPGRADES", FONT_S, GRAY, (W/2, H-S(48)), True)
        back = pygame.Rect(CONTROL_SAFE_X, H-CONTROL_SAFE_Y-S(52), S(210), S(52))
        prev = pygame.Rect(W/2-S(260), H-CONTROL_SAFE_Y-S(52), S(210), S(52))
        nxt = pygame.Rect(W/2+S(50), H-CONTROL_SAFE_Y-S(52), S(210), S(52))
        for r,label in [(back,"VOLTAR"),(prev,"< ANTERIOR"),(nxt,"PROXIMA >")]:
            pygame.draw.rect(SCREEN, PANEL2, r, border_radius=S(14)); draw_text(label, FONT_S, WHITE, r.center, True)
        self.catalog_back_rect, self.catalog_prev_rect, self.catalog_next_rect = back, prev, nxt

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
            preview=w.get("preview",False); b=pygame.Rect(r.right-S(330),r.y+S(40),S(295),S(66)); bc=DIVINE_BLUE if preview else (GREEN if equipped else (BLUE if owned else PANEL2)); pygame.draw.rect(SCREEN,bc,b,border_radius=S(14)); draw_text("PREVIA BETA" if preview else ("EQUIPADA" if equipped else ("EQUIPAR" if owned else "NAO FABRICADA")),FONT_S,DARK if bc in (GREEN,BLUE,DIVINE_BLUE) else WHITE,b.center,True)
            if owned and not equipped and not preview: self.weapon_equip_rects.append((b,w["key"]))
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
            cost_txt=f"{w['coins']} moedas | "+"  ".join(f"{FORGE_MATERIALS[k]['name']} {self.forge_material_amount(k)}/{v}" for k,v in w["cost"].items())
            draw_wrapped_text(cost_txt,FONT_S,GRAY,pygame.Rect(r.x+S(18),r.y+S(106),r.w-S(400),S(48)),1,False,2)
            preview=w.get("preview",False); b=pygame.Rect(r.right-S(345),r.y+S(48),S(310),S(68)); bc=DIVINE_BLUE if preview else (GREEN if equipped else (BLUE if owned else ORANGE)); pygame.draw.rect(SCREEN,bc,b,border_radius=S(15)); draw_text("EM BETA" if preview else ("EQUIPADA" if equipped else ("EQUIPAR" if owned else "FABRICAR")),FONT_S,DARK,b.center,True)
            if not equipped and not preview: self.forge_recipe_rects.append((b,w["key"],owned))
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
        pages = max(1, math.ceil(len(BESTIARY_ENTRIES)/per_page))
        self.bestiary_page = int(clamp(self.bestiary_page, 0, pages-1))
        subset = BESTIARY_ENTRIES[self.bestiary_page*per_page:(self.bestiary_page+1)*per_page]
        cols, gap = 2, S(22)
        top = S(120)
        card_w = int((W-SAFE*2-gap)/2)
        card_h = S(230)
        self.bestiary_train_rects=[]
        for i, item in enumerate(subset):
            col, row = i%cols, i//cols
            r = pygame.Rect(SAFE+col*(card_w+gap), top+row*(card_h+gap), card_w, card_h)
            boss = item["type"] == "Boss"
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
        labels = {"joystick":"JOYSTICK", "attack":"ATK", "dash":"DASH", "parry":"PARRY", "domain":"DOM", "pause":"PAUSE"}
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
            rarity_color = {"common":GRAY, "rare":BLUE, "epic":PURPLE, "legendary":YELLOW, "cursed":RED}
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
        rarity_color = {"common": GRAY, "rare": BLUE, "epic": PURPLE, "legendary": YELLOW, "cursed": RED}
        rarity_name = {"common": "COMUM", "rare": "RARO", "epic": "EPICO", "legendary": "LENDARIO", "cursed": "AMALDICOADO"}
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

        aw, ah, ag = S(215), S(60), S(18)
        sfx_btn = pygame.Rect(W*0.30-aw-ag//2, int(H*0.69), aw, ah)
        music_btn = pygame.Rect(W*0.30+ag//2, int(H*0.69), aw, ah)
        pygame.draw.rect(SCREEN, GREEN if AUDIO.sfx_on else PANEL2, sfx_btn, border_radius=S(14))
        pygame.draw.rect(SCREEN, GREEN if AUDIO.music_on else PANEL2, music_btn, border_radius=S(14))
        draw_text("SFX " + ("ON" if AUDIO.sfx_on else "OFF"), FONT_S, DARK if AUDIO.sfx_on else WHITE, sfx_btn.center, True)
        draw_text("MUSICA " + ("ON" if AUDIO.music_on else "OFF"), FONT_S, DARK if AUDIO.music_on else WHITE, music_btn.center, True)

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
        self.pause_sfx_rect = sfx_btn
        self.pause_music_rect = music_btn

    def draw_whats_new(self):
        SCREEN.fill(BG)
        draw_text("NOVIDADES - V13", FONT_L, WHITE, (W/2, S(52)), True)
        draw_text("ARRASTE PARA CIMA/BAIXO", FONT_S, CYAN, (W/2, S(96)), True)
        viewport=pygame.Rect(CONTROL_SAFE_X,S(128),W-CONTROL_SAFE_X*2,H-S(230))
        pygame.draw.rect(SCREEN,(20,21,29),viewport,border_radius=S(16))
        card_h=S(118); gap=S(12)
        content_h=len(WHATS_NEW)*(card_h+gap)+S(8)
        max_scroll=max(0,content_h-viewport.h)
        self.whats_new_max_scroll=max_scroll
        self.whats_new_scroll=clamp(self.whats_new_scroll,-self.whats_new_overscroll,max_scroll+self.whats_new_overscroll)
        old_clip=SCREEN.get_clip(); SCREEN.set_clip(viewport)
        y=viewport.y+S(8)-self.whats_new_scroll
        for i,line in enumerate(WHATS_NEW):
            r=pygame.Rect(viewport.x+S(10),int(y),viewport.w-S(20),card_h)
            if r.bottom>=viewport.top and r.top<=viewport.bottom:
                pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(14))
                pygame.draw.rect(SCREEN,CYAN,r,width=max(1,S(2)),border_radius=S(14))
                draw_text(str(i+1),FONT_M,YELLOW,(r.x+S(22),r.centery),True)
                draw_wrapped_text(line,FONT_S,WHITE,pygame.Rect(r.x+S(58),r.y+S(18),r.w-S(78),r.h-S(30)),2,False,3)
            y += card_h+gap
        SCREEN.set_clip(old_clip)
        # barra lateral de scroll
        if max_scroll>0:
            track=pygame.Rect(viewport.right-S(10),viewport.y+S(8),S(5),viewport.h-S(16)); pygame.draw.rect(SCREEN,PANEL2,track,border_radius=S(3))
            knob_h=max(S(35),int(track.h*viewport.h/max(content_h,1)))
            visual_scroll=clamp(self.whats_new_scroll,0,max_scroll)
            knob_y=track.y+(track.h-knob_h)*(visual_scroll/max_scroll)
            pygame.draw.rect(SCREEN,CYAN,(track.x,knob_y,track.w,knob_h),border_radius=S(3))
        back = pygame.Rect(CONTROL_SAFE_X, H-CONTROL_SAFE_Y-S(46), S(210), S(46))
        pygame.draw.rect(SCREEN, PANEL2, back, border_radius=S(14)); draw_text("VOLTAR", FONT_S, WHITE, back.center, True)
        self.whats_new_back_rect = back
        self.whats_new_viewport=viewport

    def whats_new_down(self,pos):
        if self.whats_new_back_rect.collidepoint(pos):
            self.state="menu"; return
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
            ok=key in unlocked; special=key=="meta_all"; edge=META_ACH_COLOR if special else (GREEN if ok else GRAY)
            pygame.draw.rect(SCREEN,PANEL,r,border_radius=S(15)); pygame.draw.rect(SCREEN,edge,r,width=max(2,S(4 if special else 3)),border_radius=S(15))
            draw_text(("[OK] " if ok else "[ ] ")+name,FONT_M,edge,(r.x+S(14),r.y+S(12)))
            draw_wrapped_text(desc,FONT_S,WHITE if ok else GRAY,pygame.Rect(r.x+S(14),r.y+S(56),r.w-S(28),S(58)),2,False,2)
            cur,goal,pp=self.achievement_progress(key); bar=pygame.Rect(r.x+S(14),r.bottom-S(38),r.w-S(28),S(12)); pygame.draw.rect(SCREEN,DARK,bar,border_radius=S(6)); f=bar.copy(); f.w=int(bar.w*pp/100); pygame.draw.rect(SCREEN,META_ACH_COLOR if special else (GREEN if ok else CYAN),f,border_radius=S(6))
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
            draw_text("0910 ATIVO: CODIGO-MESTRE LIBERADO",FONT_S,GREEN,(W/2,S(270)),True)

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
                self.cheat_message = "CHEAT 2026 AINDA NAO ATIVADO"
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
        if self.cheat_buffer == "0910":
            # Codigo-mestre: libera tudo que os outros codigos existentes liberam.
            SAVE["cheat_all_chars"] = True
            SAVE["cheat_money"] = True
            SAVE["cheat_dev"] = True
            save_data(SAVE)
            self.cheat_message = "0910 ACEITO: TODOS OS CODIGOS LIBERADOS"
            self.unlock_notice = "CHEAT 0910: PERSONAGENS + PAINEL DEV + DINHEIRO"
            self.unlock_notice_timer = 4.0
            AUDIO.play("unlock", 1.0)
        elif self.cheat_buffer == "2026":
            SAVE["cheat_money"] = True
            SAVE["cheat_dev"] = True
            save_data(SAVE)
            self.cheat_message = "CODIGO 2026 ACEITO: PAINEL DEV LIBERADO"
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
            AUDIO.sfx_on = bool(SAVE.get("sfx_on", True))
            AUDIO.music_on = bool(SAVE.get("music_on", True))
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
        elif self.state == "character_select":
            self.draw_character_select()
        elif self.state == "difficulty_select":
            self.draw_difficulty_select()
        elif self.state == "shop":
            self.draw_shop()
        elif self.state == "upgrade_catalog":
            self.draw_upgrade_catalog()
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

    def draw_difficulty_select(self):
        SCREEN.fill(BG)
        name = self.pending_character or self.selected_character
        draw_text("ESCOLHA A DIFICULDADE", FONT_L, WHITE, (W/2, S(70)), True)
        draw_text(f"PERSONAGEM: {name.upper()} | DIFICIL = ANTIGO FACIL DA V14", FONT_S, GRAY, (W/2, S(125)), True)
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
            if hasattr(self, "menu_sfx_rect") and self.menu_sfx_rect.collidepoint(pos):
                on = AUDIO.toggle_sfx(); SAVE["sfx_on"] = on; save_data(SAVE)
                if on: AUDIO.play("click", 0.8)
            elif hasattr(self, "menu_music_rect") and self.menu_music_rect.collidepoint(pos):
                on = AUDIO.toggle_music(); SAVE["music_on"] = on; save_data(SAVE)
                AUDIO.play("click", 0.8)
            elif self.menu_start_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.open_character_select("arena")
            elif self.menu_afk_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.open_character_select("afk")
            elif self.menu_shop_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.state = "shop"
            elif self.menu_upgrades_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.catalog_page = 0; self.state = "upgrade_catalog"
            elif self.menu_bestiary_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.bestiary_page = 0; self.state = "bestiary"
            elif self.menu_controls_rect.collidepoint(pos):
                AUDIO.play("click", 0.75); self.state = "control_editor"
            elif self.menu_news_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.whats_new_scroll=0.0; self.state = "whats_new"
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

        elif self.state == "character_select":
            if self.character_back_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "menu"
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

        elif self.state == "paused":
            if hasattr(self, "pause_sfx_rect") and self.pause_sfx_rect.collidepoint(pos):
                on = AUDIO.toggle_sfx(); SAVE["sfx_on"] = on; save_data(SAVE)
                if on: AUDIO.play("click", 0.8)
            elif hasattr(self, "pause_music_rect") and self.pause_music_rect.collidepoint(pos):
                on = AUDIO.toggle_music(); SAVE["music_on"] = on; save_data(SAVE)
                AUDIO.play("click", 0.8)
            elif self.pause_resume_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "playing"
            elif self.pause_upgrades_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.run_upgrade_page = 0; self.state = "run_upgrades"
            elif self.pause_menu_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.leave_run_to_menu()

        elif self.state == "upgrade_catalog":
            entries = self.all_upgrade_entries()
            pages = max(1, math.ceil(len(entries)/6))
            if self.catalog_back_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "menu"
            elif self.catalog_prev_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.catalog_page = (self.catalog_page - 1) % pages
            elif self.catalog_next_rect.collidepoint(pos):
                AUDIO.play("click", 0.55); self.catalog_page = (self.catalog_page + 1) % pages

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
            pages = max(1, math.ceil(len(BESTIARY_ENTRIES)/6))
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
                    elif game.state in ("upgrade_catalog", "bestiary", "control_editor", "character_select", "shop", "glonk_death", "death", "whats_new", "achievements", "missions", "cheats", "backup"):
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
                elif event.key == pygame.K_m:
                    on = AUDIO.toggle_music(); SAVE["music_on"] = on; save_data(SAVE)
                elif event.key == pygame.K_n:
                    on = AUDIO.toggle_sfx(); SAVE["sfx_on"] = on; save_data(SAVE)
                    if on: AUDIO.play("click", 0.7)

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

                if game.state == "playing":
                    if event.key == pygame.K_SPACE:
                        game.attack_held=True
                        if game.player.character == "Potential Man":
                            game.player.potential_hold_timer=0.0; game.player.potential_hold_triggered=False
                        elif game.player.has_divine_attack_hold():
                            game.player.divine_attack_hold=0.0; game.player.divine_attack_triggered=False
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
                        else: game.player.expand_domain(game)

            elif event.type == pygame.KEYUP:
                if game.state == "playing":
                    if event.key == pygame.K_SPACE:
                        if game.player.character == "Potential Man" and not game.player.potential_hold_triggered: game.player.attack(game)
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

            elif event.type == pygame.MOUSEBUTTONUP:
                if not getattr(event, "touch", False):
                    pos = to_game_pos(event.pos)
                    if game.state == "control_editor":
                        game.control_editor_up()
                    elif game.state == "character_select":
                        game.character_select_up(pos)
                    elif game.state == "whats_new":
                        game.whats_new_up(pos)
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

            elif event.type == pygame.FINGERUP:
                physical = (event.x * PHYS_W, event.y * PHYS_H)
                pos = to_game_pos(physical)
                if game.state == "control_editor":
                    game.control_editor_up()
                elif game.state == "character_select":
                    game.character_select_up(pos, event.finger_id)
                elif game.state == "whats_new":
                    game.whats_new_up(pos)
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
