import pygame
import random
import math
import json
import os
import io
import wave
from array import array
from dataclasses import dataclass

# Mixer pequeno para reduzir atraso de som em Android. Se o aparelho nao liberar
# audio, o AudioManager abaixo desativa som sem derrubar o jogo.
pygame.mixer.pre_init(22050, -16, 1, 512)
pygame.init()

# ============================================================
# DERROTE O GORDO DO PAI DO KAYK - V10 ANDROID FIX + AUDIO
# Protótipo mobile-first LANDSCAPE, sem assets externos.
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

# Resolucao-base oficial em LANDSCAPE: 2340x1080.
# Equivale ao aparelho 1080x2340 deitado. Outros tamanhos continuam responsivos.
DESIGN_W = 2340
DESIGN_H = 1080
SCALE = max(0.28, min(W / DESIGN_W, H / DESIGN_H))
SAFE = max(6, int(min(W, H) * 0.018))

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
            if pygame.mixer.get_init() is None:
                self.enabled = False
                return
            ch = pygame.mixer.find_channel(False)
            if ch is None:
                return
            ch.set_volume(clamp(self.sfx_volume * volume, 0.0, 1.0))
            ch.play(snd)
        except Exception:
            # Som nunca deve derrubar a partida.
            self.enabled = False

    def toggle_sfx(self):
        self.sfx_on = not self.sfx_on
        return self.sfx_on

    def toggle_music(self):
        self.music_on = not self.music_on
        if not self.music_on and self.enabled and self.music_channel:
            try:
                self.music_channel.stop()
            except Exception:
                # Android pode invalidar o mixer ao trocar de app/dispositivo de audio.
                self.enabled = False
            self.current_track = None
        return self.music_on

    def sync_music(self, game):
        if not self.enabled or self.music_channel is None:
            return
        if not self.music_on:
            try:
                if self.music_channel.get_busy():
                    self.music_channel.stop()
            except Exception:
                self.enabled = False
            self.current_track = None
            return
        if game.state in ("playing", "paused"):
            boss_alive = any(type(e).__name__ == "Boss" and not getattr(e, "dead", False) for e in game.enemies)
            target = "boss" if boss_alive else "arena"
            vol = self.music_volume * (0.42 if game.state == "paused" else 1.0)
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
        "hp": 82, "stamina": 118, "weapon": 3, "weapon_name": "CAJADO", "damage": 20.0, "speed": 315,
        "regen": 11.5, "color": PINK, "domain": "REALIDADE SEM SAIDA",
        "desc": "Pouco HP | Cajado | Invoca mini-Anas explosivas",
        "domain_desc": "Cajado recarrega em 1s e as explosoes ficam muito mais fortes",
    },
    "Kevyn": {
        "hp": 240, "stamina": 190, "weapon": 0, "weapon_name": "ESPADA", "damage": 18.0, "speed": 250,
        "regen": 9.0, "color": BLUE, "domain": "TRONO FORA DO TEMPO",
        "desc": "MUITO HP + estamina | Espada | Resistente",
        "domain_desc": "Invulneravel e 2x velocidade no dominio",
    },
    "Ycaro": {
        "hp": 135, "stamina": 132, "weapon": 2, "weapon_name": "SHOTGUN", "damage": 16.0, "speed": 288,
        "regen": 10.0, "color": ORANGE, "domain": "CAMPO DE CACA DO ZUMBI",
        "desc": "Equilibrado | Shotgun | Medio alcance",
        "domain_desc": "Mira automatica e sem cooldown no dominio",
    },
    "Kayk": {
        "hp": 125, "stamina": 155, "weapon": 4, "weapon_name": "PISTOLAS DUPLAS", "damage": 15.0, "speed": 300,
        "regen": 11.0, "color": PURPLE, "domain": "NECROPOLE DAS ALMAS",
        "desc": "Duas pistolas | Dois tiros por ataque | Desbloqueavel",
        "domain_desc": "Almas disparam automaticamente nos inimigos dentro do dominio",
    },
    "Glonk": {
        "hp": 100, "stamina": 0, "weapon": 5, "weapon_name": "NADA", "damage": 0.0, "speed": 0,
        "regen": 0.0, "color": GRAY, "domain": "NENHUM",
        "desc": "não faz nada e morre",
        "domain_desc": "Glonk nao possui expansao de dominio",
    },
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
        ("rare", "CORRIDA CURTA", "+45% dano se a mini-Ana viajar bastante ate o alvo", "ana_blind_spot"),
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
    "Glonk": [],
}

STACKABLE_UPGRADES = {"heart_reinforced", "steel_lung", "second_wind", "heavy_hand", "quick_feet", "scavenger", "pierce", "crit"}

SAVE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "energia_vital_save.json")

DEFAULT_SAVE = {
    "coins": 0,
    "vitality_level": 0,
    "damage_level": 0,
    "speed_level": 0,
    "best_wave": 0,
    "best_kills": 0,
    "kayk_unlocked": False,
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

SAVE = load_save()
AUDIO = AudioManager(SAVE)


def clamp(v, a, b):
    return max(a, min(b, v))


def vec_from_angle(a):
    return pygame.Vector2(math.cos(a), math.sin(a))


def draw_text(text, font, color, pos, center=False):
    img = font.render(str(text), True, color)
    rect = img.get_rect()
    if center:
        rect.center = pos
    else:
        rect.topleft = pos
    SCREEN.blit(img, rect)
    return rect


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
        pygame.draw.circle(SCREEN, self.color, (int(self.pos.x + offset.x), int(self.pos.y + offset.y)), self.radius)
        pygame.draw.circle(SCREEN, WHITE, (int(self.pos.x + offset.x), int(self.pos.y + offset.y)), max(1, self.radius // 3))


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


class Drop:
    COLORS = {"heal": GREEN, "stamina": CYAN, "shield": BLUE, "haste": YELLOW, "coin": ORANGE}

    def __init__(self, pos, kind):
        self.pos = pygame.Vector2(pos)
        self.kind = kind
        self.radius = S(20 if kind in ("heal", "stamina") else 18)
        self.t = 0
        self.life = 12

    def update(self, dt):
        self.t += dt
        self.life -= dt
        return self.life > 0

    def draw(self, offset):
        p = self.pos + pygame.Vector2(0, math.sin(self.t * 5) * S(5)) + offset
        color = self.COLORS[self.kind]
        # Cura e estamina sao orbes com brilho para ficarem faceis de identificar.
        if self.kind in ("heal", "stamina"):
            pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius + S(7), S(4))
        pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius)
        label = {"heal": "+", "stamina": "E", "shield": "S", "haste": ">", "coin": "$"}[self.kind]
        draw_text(label, FONT_S, DARK, p, True)


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
        self.coin_value = 2

        base_hp = 26 + wave * 7
        base_speed = S(95 + wave * 2.2)
        self.contact_damage = 7 + wave * 0.7

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

    def damage(self, amount, game, source_pos=None):
        if self.dead:
            return
        if self.elite == "armored":
            amount *= 0.72
        self.hp -= amount
        self.flash = 0.12
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
        reward = int(self.coin_value * game.coin_multiplier)
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

    def update(self, dt, game):
        if self.dead:
            return
        self.flash = max(0, self.flash - dt)
        self.shoot_cd -= dt
        self.touch_cd -= dt

        to_player = game.player.pos - self.pos
        dist = max(1, to_player.length())
        direction = to_player / dist

        if self.kind == "chaser" or self.kind == "tank":
            self.pos += direction * self.speed * dt
        elif self.kind == "shooter":
            if dist > S(470):
                self.pos += direction * self.speed * dt
            elif dist < S(300):
                self.pos -= direction * self.speed * dt
            if self.shoot_cd <= 0:
                speed = S(300 + game.wave * 5)
                game.projectiles.append(Projectile(self.pos, direction * speed, 7 + game.wave * 0.55, "enemy"))
                self.shoot_cd = max(0.55, 1.45 - game.wave * 0.02)
        elif self.kind == "kiter":
            tangent = pygame.Vector2(-direction.y, direction.x)
            if dist < S(360):
                move = -direction * 0.8 + tangent * 0.65
            else:
                move = direction * 0.35 + tangent * 0.8
            if move.length_squared() > 0:
                self.pos += move.normalize() * self.speed * dt
            if self.shoot_cd <= 0:
                for off in (-0.12, 0.12):
                    a = math.atan2(direction.y, direction.x) + off
                    game.projectiles.append(Projectile(self.pos, vec_from_angle(a) * S(330), 5 + game.wave * 0.45, "enemy", S(8), YELLOW))
                self.shoot_cd = 1.8

        # contato
        if dist < self.radius + game.player.radius and self.touch_cd <= 0:
            game.player.take_damage(self.contact_damage, game)
            self.touch_cd = 0.75
            if direction.length_squared() > 0:
                game.player.pos += direction * S(28)

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
    """Alvo imortal da Zona AFK: nao anda, nao ataca e reseta o HP ao cair."""
    def __init__(self, pos, wave=1):
        super().__init__(pos, "tank", wave, None)
        self.max_hp = 260
        self.hp = self.max_hp
        self.radius = S(42)
        self.speed = 0
        self.contact_damage = 0
        self.color = (120, 125, 145)
        self.coin_value = 0

    def update(self, dt, game):
        self.flash = max(0, self.flash - dt)
        self.marked = self.hp <= self.max_hp * 0.18 and self.hp > 0

    def die(self, game):
        # Nao desaparece: serve para testar combo, execucao e dano infinitamente.
        self.dead = False
        self.hp = self.max_hp
        self.marked = False
        self.blood_marked = False
        game.combo = min(50, game.combo + 1)
        game.combo_timer = 3.0
        game.on_enemy_killed(self)
        game.spawn_particles(self.pos, self.color, 18)
        game.damage_texts.append(DamageText("DUMMY RESET", pygame.Vector2(self.pos), CYAN))

    def draw(self, offset):
        super().draw(offset)
        p = self.pos + offset
        draw_text("DUMMY", FONT_S, CYAN, (p.x, p.y + self.radius + S(24)), True)


class Boss(Enemy):
    def __init__(self, pos, wave):
        super().__init__(pos, "tank", wave, None)
        self.radius = S(72)
        self.max_hp = 700 + wave * 95
        self.hp = self.max_hp
        self.speed = S(75 + wave)
        self.color = (160, 50, 70)
        self.coin_value = 55
        self.wave = wave
        self.name = "PAI DO KAYK" if wave == 5 else "O DEVORADOR"
        self.burst_cd = 1.0
        self.charge_cd = 3.0
        self.charging = 0
        self.charge_dir = pygame.Vector2()

    def die(self, game):
        if self.dead:
            return
        first_father_kill = self.wave == 5 and game.mode == "arena" and not SAVE.get("kayk_unlocked", False)
        super().die(game)
        if first_father_kill:
            SAVE["kayk_unlocked"] = True
            save_data(SAVE)
            AUDIO.play("unlock", 1.0)
            game.unlock_notice = "KAYK DESBLOQUEADO!"
            game.unlock_notice_timer = 5.0

    def update(self, dt, game):
        if self.dead:
            return
        self.flash = max(0, self.flash - dt)
        self.burst_cd -= dt
        self.charge_cd -= dt
        self.touch_cd -= dt
        to_player = game.player.pos - self.pos
        dist = max(1, to_player.length())
        d = to_player / dist
        phase2 = self.hp <= self.max_hp * 0.5

        if self.charging > 0:
            self.charging -= dt
            self.pos += self.charge_dir * self.speed * (4.3 if phase2 else 3.4) * dt
        else:
            self.pos += d * self.speed * (1.25 if phase2 else 0.85) * dt
            if self.charge_cd <= 0:
                self.charging = 0.55
                self.charge_dir = pygame.Vector2(d)
                self.charge_cd = 2.4 if phase2 else 3.7

        if self.burst_cd <= 0:
            shots = 14 if phase2 else 9
            for i in range(shots):
                a = i * math.tau / shots + game.time * 0.35
                game.projectiles.append(Projectile(self.pos, vec_from_angle(a) * S(285 if phase2 else 235), 8 + game.wave * 0.5, "enemy", S(11), PINK))
            self.burst_cd = 1.15 if phase2 else 1.9
            game.shake = max(game.shake, S(5))

        if dist < self.radius + game.player.radius and self.touch_cd <= 0:
            game.player.take_damage(14 + game.wave * 0.8, game)
            self.touch_cd = 0.65

        self.pos.x = clamp(self.pos.x, self.radius, W - self.radius)
        self.pos.y = clamp(self.pos.y, S(180) + self.radius, H - S(335) - self.radius)

    def draw(self, offset):
        super().draw(offset)
        p = self.pos + offset
        draw_text(self.name, FONT_S, WHITE, (p.x, p.y + self.radius + S(24)), True)


class Player:
    def __init__(self, game, character="Ycaro"):
        self.character = character if character in CHARACTER_CONFIG else "Ycaro"
        cfg = CHARACTER_CONFIG[self.character]
        self.radius = S(28)
        self.pos = pygame.Vector2(W / 2, H * 0.62)
        self.facing = pygame.Vector2(0, -1)
        self.color = cfg["color"]
        self.base_speed = S(cfg["speed"]) * (1 + 0.03 * SAVE["speed_level"])
        self.speed_mult = 1.0
        self.speed_buff = 0
        self.still_timer = 0.0

        self.max_hp = cfg["hp"] + SAVE["vitality_level"] * 8
        self.hp = self.max_hp
        self.max_stamina = cfg["stamina"] + SAVE["vitality_level"] * 6
        self.stamina = self.max_stamina
        self.stamina_regen = cfg["regen"]
        self.stamina_regen_delay = 0.0

        self.base_damage = cfg["damage"] * (1 + 0.08 * SAVE["damage_level"])
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
        self.weapons = ["ESPADA", "PISTOLA", "SHOTGUN", "CAJADO", "PISTOLAS DUPLAS", "NADA"]
        self.domain_name = cfg["domain"]

        # Flags/valores de build. As cartas ligam estes efeitos durante a run.
        self.projectile_pierce = 0
        self.projectile_bonus = 1.0
        self.stamina_on_hit = 1.0
        self.execute_bonus = 0
        self.crit_chance = 0.0
        self.drop_bonus = 0.0
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
        cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
        self.stamina = clamp(self.stamina + amount, 0, cap)
        if game and self.stamina > old:
            game.damage_texts.append(DamageText("+" + str(int(self.stamina-old)) + " STA", pygame.Vector2(self.pos), CYAN))

    def heal(self, amount, game=None):
        if game and getattr(game, "healing_locked", False):
            return
        old = self.hp
        self.hp = clamp(self.hp + amount, 0, self.max_hp)
        if game and self.hp > old:
            game.damage_texts.append(DamageText("+" + str(int(self.hp-old)) + " HP", pygame.Vector2(self.pos), GREEN))

    def effective_damage_mult(self, game, enemy=None, source="generic", distance=None):
        m = self.damage_mult * game.player_event_damage_mult
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
        return m

    def take_damage(self, amount, game):
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
        if self.character == "Kevyn" and self.kevyn_immovable and self.still_timer >= 0.8:
            amount *= 0.55
        if self.no_brakes:
            amount *= 1.25
        self.hp -= amount
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

    def attack(self, game):
        if self.character == "Glonk":
            return
        ycaro_domain = self.character == "Ycaro" and self.in_domain(game)
        if self.attack_cd > 0 and not ycaro_domain:
            return
        if game.state != "playing":
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
            self.attack_cd = 0.16 if kevyn_domain_evo else 0.28
            rng = S(122) * self.kevyn_sword_range * (1.20 if kevyn_domain_evo else 1.0)
            angle_limit = math.cos(math.radians(72))
            hit_any = False
            for e in list(game.enemies):
                if e.dead:
                    continue
                to_e = e.pos - self.pos
                dist = to_e.length()
                if 0 < dist <= rng + e.radius:
                    d = to_e / dist
                    if d.dot(self.facing) >= angle_limit:
                        dmg = self.base_damage * self.effective_damage_mult(game, e, "sword", dist)
                        if random.random() < self.crit_chance:
                            dmg *= 2
                            game.damage_texts.append(DamageText("CRIT!", pygame.Vector2(e.pos), YELLOW))
                        game.current_damage_kind = "sword"
                        e.damage(dmg, game, self.pos)
                        game.current_damage_kind = None
                        self.recover_stamina(self.stamina_on_hit, game)
                        hit_any = True
            AUDIO.play("kevyn_sword", 0.72, 90)
            game.slash_fx = 0.12
            if hit_any:
                game.register_combo_hit()
            return

        # Ana: cajado. Invoca pequenas Anas que correm ate o inimigo e explodem.
        if self.character == "Ana":
            if not self.spend_stamina(9):
                return
            in_dom = self.in_domain(game)
            # V8: dentro da Expansao, o cajado recarrega em 1 segundo; fora dela, 3 segundos.
            self.attack_cd = 1.0 if in_dom else 3.0
            count = 2 + (1 if self.ana_double_shot else 0)
            base_angle = math.atan2(self.facing.y, self.facing.x)
            for i in range(count):
                spread = (i-(count-1)/2) * 0.45
                spawn = self.pos + vec_from_angle(base_angle + spread) * S(30)
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
            game.damage_texts.append(DamageText("MINI-ANAS!", pygame.Vector2(self.pos), PINK))
            return

        # Kayk: duas pistolas. Cada ataque dispara um par de balas.
        if self.character == "Kayk":
            if not self.spend_stamina(5):
                return
            self.attack_cd = 0.24
            if self.in_domain(game):
                self._auto_aim(game, domain_only=True)
            pairs = 1 + self.kayk_extra_pair
            base_a = math.atan2(self.facing.y, self.facing.x)
            offsets = (-0.055, 0.055)
            for pair in range(pairs):
                pair_shift = (pair - (pairs-1)/2) * 0.08
                for off in offsets:
                    d = vec_from_angle(base_a + off + pair_shift)
                    pr = Projectile(self.pos + d*S(36), d*S(790), self.base_damage*0.78*self.projectile_bonus, "player", S(7), PURPLE, 2.0, self.projectile_pierce + self.kayk_soul_pierce)
                    pr.kind = "dual_pistol"
                    pr.origin = pygame.Vector2(self.pos)
                    game.projectiles.append(pr)
            AUDIO.play("kayk_dual", 0.70, 70)
            return

        # Ycaro: shotgun.
        if self.character == "Ycaro":
            if not self.spend_stamina(7):
                return
            self.attack_cd = 0.035 if ycaro_domain else 0.58
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

    def dash(self, game, move_dir):
        if self.character == "Glonk" or self.dash_cd > 0 or self.dash_time > 0:
            return
        dash_cost = 3 if self.character == "Kayk" and self.kayk_spectral_step else 5
        if not self.spend_stamina(dash_cost):
            return
        if move_dir.length_squared() == 0:
            move_dir = pygame.Vector2(self.facing)
        self.dash_dir = move_dir.normalize()
        special_dash = self.ana_vector_step or (self.character == "Kayk" and self.kayk_spectral_step)
        self.dash_time = 0.24 if special_dash else 0.18
        self.dash_cd = 0.50 if special_dash else 0.72
        self.invuln = 0.27 if special_dash else 0.22
        AUDIO.play("dash", 0.58, 70)

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
        if self.character == "Glonk" or self.parry_cd > 0:
            return
        if not self.spend_stamina(3):
            return
        self.parry_time = 0.16
        self.parry_cd = 0.8

    def expand_domain(self, game):
        if self.character == "Glonk" or game.domain_charge < 100 or game.domain_active:
            return
        if self.devil_pact:
            cost = self.max_hp * 0.12
            if self.hp <= cost + 1:
                return
            self.hp -= cost
        game.domain_charge = 0
        AUDIO.play("domain", 1.0, 250)
        game.shake = max(game.shake, S(16))
        game.flash_screen = max(game.flash_screen, 0.14)
        game.domain_center = pygame.Vector2(self.pos)
        game.domain_radius = S(535)
        game.domain_duration = 8.0 + (2.0 if self.domain_evolution else 0.0)
        if (self.character == "Ana" and self.ana_reality_exe) or (self.character == "Kevyn" and self.kevyn_time_stops) or (self.character == "Ycaro" and self.ycaro_no_too_close) or (self.character == "Kayk" and self.kayk_thousand_souls):
            game.domain_duration += 1.5
        game.domain_active = True
        game.domain_timer = game.domain_duration
        game.domain_name = self.domain_name
        game.domain_message_timer = 1.65
        game.attack_held = False
        game.kayk_domain_fire_cd = 0.0
        self.stamina = min(self.max_stamina * (1.30 if self.beyond_limit else 1.0), self.stamina + self.max_stamina * 0.35)
        # Efeito especial do Kevyn acontece imediatamente, sem cutscene/overlay pesado.
        if self.character == "Kevyn" and self.kevyn_time_stops:
            for pr in game.projectiles:
                if pr.owner == "enemy" and game.is_in_domain(pr.pos):
                    pr.owner = "player"
                    pr.vel *= -1.5
                    pr.damage *= 2.0
                    pr.color = BLUE
                    pr.parry_reflected = True

    def update(self, dt, game, move_dir):
        self.attack_cd = max(0, self.attack_cd - dt)
        self.dash_cd = max(0, self.dash_cd - dt)
        self.parry_cd = max(0, self.parry_cd - dt)
        self.parry_time = max(0, self.parry_time - dt)
        self.invuln = max(0, self.invuln - dt)
        self.speed_buff = max(0, self.speed_buff - dt)
        self.predator_timer = max(0, self.predator_timer - dt)

        if self.character == "Glonk":
            # O destino inevitavel de Glonk: ~2.2 segundos, independente de upgrades permanentes.
            self.hp -= self.max_hp * 0.48 * dt
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
        self.speed_mult = speed_mult

        self.stamina_regen_delay = max(0, self.stamina_regen_delay - dt)
        regen = self.stamina_regen
        if self.last_breath and self.hp <= self.max_hp * 0.25:
            regen *= 2.0
        if self.stamina_regen_delay <= 0 and self.dash_time <= 0:
            cap = self.max_stamina * (1.30 if self.beyond_limit else 1.0)
            self.stamina = min(cap, self.stamina + regen * dt)

        if self.dash_time > 0:
            self.dash_time -= dt
            self.pos += self.dash_dir * self.base_speed * (3.7 if (self.ana_vector_step or (self.character == "Kayk" and self.kayk_spectral_step)) else 3.2) * dt
            game.spawn_particles(self.pos, CYAN, 1)
        elif move_dir.length_squared() > 0:
            d = move_dir.normalize()
            self.facing = d
            self.pos += d * self.base_speed * self.speed_mult * dt

        self.pos.x = clamp(self.pos.x, self.radius, W - self.radius)
        self.pos.y = clamp(self.pos.y, S(205) + self.radius, H - S(335) - self.radius)

    def draw(self, offset, game):
        p = self.pos + offset
        color = self.color if self.invuln <= 0 else WHITE
        pygame.draw.circle(SCREEN, color, (int(p.x), int(p.y)), self.radius)
        pygame.draw.line(SCREEN, DARK, (int(p.x), int(p.y)), (int(p.x + self.facing.x * S(36)), int(p.y + self.facing.y * S(36))), S(7))
        if self.shield > 0:
            pygame.draw.circle(SCREEN, BLUE, (int(p.x), int(p.y)), self.radius + S(10), S(4))
        if self.parry_time > 0:
            pygame.draw.circle(SCREEN, YELLOW, (int(p.x), int(p.y)), S(80), S(8))
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
        self.upgrade_return_mode = "arena"
        self.player = Player(self, self.selected_character)
        self.enemies = []
        self.projectiles = []
        self.summons = []
        self.drops = []
        self.particles = []
        self.damage_texts = []
        self.wave = 1
        self.kills = 0
        self.score = 0
        self.run_coins = 0
        self.combo = 0
        self.combo_timer = 0
        self.domain_charge = 0
        self.domain_active = False
        self.domain_timer = 0.0
        self.domain_duration = 8.0
        self.domain_center = pygame.Vector2(W/2, H/2)
        self.domain_radius = S(535)
        # V8: sem cutscene/overlay de dominio. Apenas mensagem curta + efeito.
        self.domain_cutscene_timer = 0.0
        self.domain_cutscene_total = 0.0
        self.domain_pending = False
        self.domain_name = ""
        self.domain_message_timer = 0.0
        self.kayk_domain_fire_cd = 0.0
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
        self.achievement = ""
        self.achievement_timer = 0
        self.move_touch = {"up": False, "down": False, "left": False, "right": False}
        self.active_fingers = {}
        self.buttons = self.make_buttons()
        self.afk_buttons = self.make_afk_buttons()
        self.wave_banner = 0
        self.wave_clear_lock = False
        self.owned_upgrades = set()
        self.synergies = set()
        self.synergy_name = ""
        self.synergy_timer = 0.0
        self.enemy_slow_timer = 0.0
        self.delayed_blasts = []
        self.current_damage_kind = None
        self.healing_locked = False
        self.attack_held = False
        self.orb_chain_count = 0
        self.orb_chain_timer = 0.0
        self.kevyn_sword_kills = 0
        self.kevyn_sword_kill_timer = 0.0
        self.unlock_notice = ""
        self.unlock_notice_timer = 0.0

    def make_buttons(self):
        b = {}
        # LANDSCAPE: controles deliberadamente maiores, com espacamento amplo.
        # A escala usa a tela 2340x1080 como referencia e continua responsiva.
        unit = max(S(118), min(S(160), int(H * 0.145)))
        gap = max(S(18), int(unit * 0.14))
        edge_x = SAFE + S(34)
        bottom = H - SAFE - S(28)

        # D-pad inferior esquerdo. Cruz aberta: botoes grandes sem se encostarem.
        cx = edge_x + unit + gap
        base_y = bottom - unit
        b["left"] = pygame.Rect(cx - unit - gap, base_y, unit, unit)
        b["down"] = pygame.Rect(cx, base_y, unit, unit)
        b["right"] = pygame.Rect(cx + unit + gap, base_y, unit, unit)
        b["up"] = pygame.Rect(cx, base_y - unit - gap, unit, unit)

        # Acoes inferior direito. ATK e o maior e fica mais afastado dos extras.
        attack = max(S(155), min(S(195), int(H * 0.178)))
        small = max(S(126), min(S(158), int(attack * 0.80)))
        domain_size = max(S(118), min(S(146), int(attack * 0.74)))
        action_gap = max(S(28), int(attack * 0.16))

        ax = W - SAFE - S(42) - attack
        ay = bottom - attack
        b["attack"] = pygame.Rect(ax, ay, attack, attack)

        # DASH e PARRY em coluna, deixando um corredor livre ate o ATK.
        sx = ax - action_gap - small
        b["dash"] = pygame.Rect(sx, bottom - small, small, small)
        b["parry"] = pygame.Rect(sx, bottom - small*2 - action_gap, small, small)

        # Dominio acima do ataque, mas com folga real para nao tocar nos demais.
        b["domain"] = pygame.Rect(ax + (attack-domain_size)//2, ay - action_gap - domain_size, domain_size, domain_size)

        # Pause sempre visivel no topo central, longe das barras de HP/Dominio.
        pw, ph = S(160), S(66)
        b["pause"] = pygame.Rect(W//2-pw//2, SAFE+S(18), pw, ph)

        return b

    def make_afk_buttons(self):
        # Bancada de testes compacta no alto; nao disputa espaco com os controles.
        labels = ["DUMMY", "TIRO", "DOM", "UP"]
        gap = max(S(14), int(W * 0.008))
        bw = max(S(180), min(S(245), int(W * 0.105)))
        bh = max(S(58), min(S(74), int(H * 0.065)))
        total = bw * 4 + gap * 3
        x = W/2 - total/2
        y = SAFE + S(150)
        out = {}
        for label in labels:
            out[label] = pygame.Rect(int(x), y, bw, bh)
            x += bw + gap
        return out

    def reset_run(self, character=None):
        chosen = character or self.selected_character
        self.__init__()
        self.selected_character = chosen
        self.state = "playing"
        self.mode = "arena"
        self.player = Player(self, chosen)
        self.start_ticks = pygame.time.get_ticks()
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
        self.state = "character_select"

    def spawn_training_dummy(self):
        # Mantem no maximo 3 alvos para nao lotar a sala sem querer.
        dummies = [e for e in self.enemies if isinstance(e, TrainingDummy)]
        if len(dummies) >= 3:
            return
        slots = [(W * 0.67, H * 0.43), (W * 0.70, H * 0.57), (W * 0.55, H * 0.50)]
        self.enemies.append(TrainingDummy(slots[len(dummies)]))

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
        self.wave_banner = 1.7
        self.wave_clear_lock = False
        self.choose_event()
        if self.wave % 5 == 0:
            boss = Boss((W/2, S(350)), self.wave)
            boss.speed *= self.enemy_speed_mult * self.enemy_perma_speed_mult
            boss.contact_damage *= self.enemy_damage_mult
            self.enemies.append(boss)
            AUDIO.play("boss", 0.95, 500)
            adds = min(3, self.wave // 5)
            for _ in range(adds):
                self.enemies.append(Enemy(self.random_spawn_pos(), random.choice(["chaser", "shooter"]), self.wave))
        else:
            count = min(4 + self.wave * 2, 28)
            kinds = ["chaser", "shooter"]
            if self.wave >= 2:
                kinds.append("kiter")
            if self.wave >= 3:
                kinds.append("tank")
            elite_chance = min(0.08 + self.wave * 0.015, 0.35)
            for _ in range(count):
                kind = random.choice(kinds)
                elite = None
                if random.random() < elite_chance:
                    elite = random.choice(["frenzy", "giant", "armored", "explosive"])
                e = Enemy(self.random_spawn_pos(), kind, self.wave, elite)
                e.speed *= self.enemy_speed_mult * self.enemy_perma_speed_mult
                e.contact_damage *= self.enemy_damage_mult
                self.enemies.append(e)

    def end_run(self):
        if self.player.character == "Glonk":
            AUDIO.play("glonk", 1.0)
            self.state = "glonk_death"
            self.attack_held = False
            for key in self.move_touch:
                self.move_touch[key] = False
            return
        if self.mode == "afk":
            # Laboratorio: nao existe Game Over. Ao morrer, HP e estamina voltam cheios.
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
        SAVE["coins"] += self.run_coins
        SAVE["best_wave"] = max(SAVE["best_wave"], self.wave)
        SAVE["best_kills"] = max(SAVE["best_kills"], self.kills)
        save_data(SAVE)

    def add_domain_charge(self, amount):
        mult = 2.0 if self.player.devil_pact else 1.0
        self.domain_charge = clamp(self.domain_charge + amount * mult, 0, 100)

    def is_in_domain(self, pos):
        return self.domain_active and pygame.Vector2(pos).distance_to(self.domain_center) <= self.domain_radius

    def register_combo_hit(self):
        self.combo = min(50, self.combo + 1)
        self.combo_timer = 3.0
        if self.player.vampire_heart and self.combo > 0 and self.combo % 8 == 0:
            self.player.heal(max(2, self.player.max_hp * 0.025), self)

    def on_enemy_killed(self, enemy):
        self.add_domain_charge(8)
        p = self.player
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

    def open_upgrade(self):
        if self.state != "playing":
            return
        self.upgrade_return_mode = self.mode
        self.attack_held = False
        self.state = "upgrade"
        self.upgrade_cards = self.generate_upgrades(3)

    def generate_upgrades(self, n):
        pool = UNIVERSAL_UPGRADES + CHARACTER_UPGRADES.get(self.player.character, [])
        available = [c for c in pool if c[3] in STACKABLE_UPGRADES or c[3] not in self.owned_upgrades]
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

        if key == "heart_reinforced": p.max_hp += 20; p.heal(20)
        elif key == "steel_lung": p.max_stamina += 20; p.recover_stamina(20)
        elif key == "second_wind": p.stamina_regen *= 1.25
        elif key == "heavy_hand": p.damage_mult *= 1.15
        elif key == "quick_feet": p.base_speed *= 1.10
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
            p.glass_cannon = True; p.damage_mult *= 2.0; p.max_hp = max(30, p.max_hp*0.65); p.hp = min(p.hp, p.max_hp)
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
    def handle_touch_down(self, pos, finger_id=None):
        if self.state == "playing":
            if self.buttons["pause"].collidepoint(pos):
                self.pause_game()
                return
            if self.mode == "afk":
                if self.afk_buttons["DUMMY"].collidepoint(pos):
                    self.spawn_training_dummy()
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
            for d in ("up", "down", "left", "right"):
                if self.buttons[d].collidepoint(pos):
                    self.move_touch[d] = True
                    if finger_id is not None:
                        self.active_fingers[finger_id] = d
                    return
            if self.buttons["attack"].collidepoint(pos):
                self.attack_held = True
                if finger_id is not None:
                    self.active_fingers[finger_id] = "attack"
                self.player.attack(self)
            elif self.buttons["dash"].collidepoint(pos):
                if finger_id is not None:
                    self.active_fingers[finger_id] = "action"
                self.player.dash(self, self.get_move_dir())
            elif self.buttons["parry"].collidepoint(pos):
                self.player.parry(self)
            elif self.buttons["domain"].collidepoint(pos):
                self.player.expand_domain(self)

    def handle_touch_up(self, pos, finger_id=None):
        if finger_id is not None:
            action = self.active_fingers.pop(finger_id, None)
            if action in self.move_touch:
                self.move_touch[action] = False
            elif action == "attack":
                self.attack_held = False
        else:
            # mouse/desktop: não há ID de dedo
            for d in self.move_touch:
                self.move_touch[d] = False
            self.attack_held = False

    def get_move_dir(self):
        k = pygame.key.get_pressed()
        x = (1 if k[pygame.K_d] or k[pygame.K_RIGHT] else 0) - (1 if k[pygame.K_a] or k[pygame.K_LEFT] else 0)
        y = (1 if k[pygame.K_s] or k[pygame.K_DOWN] else 0) - (1 if k[pygame.K_w] or k[pygame.K_UP] else 0)
        x += (1 if self.move_touch["right"] else 0) - (1 if self.move_touch["left"] else 0)
        y += (1 if self.move_touch["down"] else 0) - (1 if self.move_touch["up"] else 0)
        return pygame.Vector2(x, y)

    def update_playing(self, dt):
        self.time += dt
        self.domain_message_timer = max(0, self.domain_message_timer - dt)
        self.unlock_notice_timer = max(0, self.unlock_notice_timer - dt)
        self.wave_banner = max(0, self.wave_banner - dt)
        self.slash_fx = max(0, self.slash_fx - dt)
        self.flash_screen = max(0, self.flash_screen - dt)
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
            self.domain_timer -= dt
            if self.domain_timer <= 0:
                self.domain_active = False
                self.domain_timer = 0
                self.damage_texts.append(DamageText("DOMINIO ENCERRADO", pygame.Vector2(self.player.pos), GRAY))

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
                base_cd = 0.34 if self.player.kayk_armed_procession else 0.52
                if self.player.domain_evolution:
                    base_cd *= 0.90
                self.kayk_domain_fire_cd = base_cd

        move_dir = self.get_move_dir()
        self.player.update(dt, self, move_dir)
        if self.state != "playing":
            return
        if self.attack_held:
            self.player.attack(self)

        # Atualiza invocacoes da Ana.
        self.summons = [summon for summon in self.summons if summon.update(dt, self)]

        slow_factor = 0.45 if self.enemy_slow_timer > 0 else 1.0
        for e in self.enemies:
            e.update(dt * slow_factor, self)
        self.enemies = [e for e in self.enemies if not e.dead]

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
            proj_dt = dt * (slow_factor if pr.owner == "enemy" else 1.0)
            if not pr.update(proj_dt):
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

                if pr.pos.distance_to(self.player.pos) <= pr.radius + self.player.radius:
                    if self.player.dash_time <= 0:
                        self.player.take_damage(pr.damage, self)
                    continue
            else:
                hit = False
                for e in list(self.enemies):
                    if e.id in pr.hit_ids or e.dead:
                        continue
                    if pr.pos.distance_to(e.pos) <= pr.radius + e.radius:
                        source = getattr(pr, "kind", "projectile")
                        origin = getattr(pr, "origin", self.player.pos)
                        dist = e.pos.distance_to(origin)
                        dmg = pr.damage * self.player.effective_damage_mult(self, e, source, dist)
                        if random.random() < self.player.crit_chance:
                            dmg *= 2
                            self.damage_texts.append(DamageText("CRIT!", pygame.Vector2(e.pos), YELLOW))
                        self.current_damage_kind = source
                        e.damage(dmg, self, pr.pos)
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

                        # Parry Explosivo / Paradoxo Balistico
                        if getattr(pr, "parry_reflected", False) and self.player.explosive_parry:
                            old = self.current_damage_kind
                            self.current_damage_kind = "parry_explosion"
                            for other in list(self.enemies):
                                if not other.dead and other is not e and other.pos.distance_to(e.pos) <= S(145):
                                    other.damage(pr.damage*0.75, self, e.pos)
                            self.current_damage_kind = old

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

                        if pr.pierce > 0:
                            pr.pierce -= 1
                        else:
                            hit = True
                            break
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
                if d.kind == "heal":
                    AUDIO.play("heal", 0.82, 60)
                    if self.player.insatiable_hunger:
                        self.damage_texts.append(DamageText("FOME", pygame.Vector2(self.player.pos), RED))
                    else:
                        self.player.heal(max(22, self.player.max_hp * 0.18), self)
                    if self.player.questionable_hemo:
                        self.player.recover_stamina(max(12, self.player.max_stamina*0.12), self)
                elif d.kind == "stamina":
                    AUDIO.play("stamina", 0.82, 60)
                    self.player.recover_stamina(max(28, self.player.max_stamina * 0.25), self)
                elif d.kind == "shield": AUDIO.play("pickup", 0.70, 50); self.player.shield += 1
                elif d.kind == "haste": AUDIO.play("pickup", 0.70, 50); self.player.speed_buff = 8
                elif d.kind == "coin": AUDIO.play("pickup", 0.62, 45); self.run_coins += int(8 * self.coin_multiplier)
                self.spawn_particles(d.pos, Drop.COLORS[d.kind], 9)
                if self.player.orb_magnet and d.kind in ("heal","stamina"):
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

        if self.parries >= 5 and self.achievement != "MESTRE DO PARRY":
            self.achievement = "MESTRE DO PARRY"; self.achievement_timer = 3
        if self.perfect_dodges >= 5 and self.achievement != "INTOCAVEL":
            self.achievement = "INTOCAVEL"; self.achievement_timer = 3

        if self.mode == "afk":
            self.player.hp = min(self.player.max_hp, self.player.hp + self.player.max_hp * 0.08 * dt)
            cap = self.player.max_stamina * (1.30 if self.player.beyond_limit else 1.0)
            self.player.stamina = min(cap, self.player.stamina + 18.0 * dt)
            if not any(isinstance(e, TrainingDummy) for e in self.enemies):
                self.spawn_training_dummy()
        elif not self.enemies and not self.wave_clear_lock and self.state == "playing":
            self.wave_clear_lock = True
            self.player.heal(10, self)
            self.player.recover_stamina(18, self)
            AUDIO.play("wave_clear", 0.85)
            self.open_upgrade()

    def update(self, dt):
        if self.state == "playing":
            self.update_playing(dt)
        elif self.state in ("menu", "character_select", "shop", "upgrade", "death", "glonk_death"):
            self.particles = [p for p in self.particles if p.update(dt)]
            self.damage_texts = [d for d in self.damage_texts if d.update(dt)]
        AUDIO.sync_music(self)

    def draw_bg(self):
        SCREEN.fill(BG)
        grid = S(80)
        map_top = S(165)
        map_bottom = H - S(335)
        for x in range(0, W, grid):
            pygame.draw.line(SCREEN, (24, 26, 34), (x, map_top), (x, map_bottom), 1)
        for y in range(map_top, map_bottom, grid):
            pygame.draw.line(SCREEN, (24, 26, 34), (0, y), (W, y), 1)

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
        # V8: propositalmente sem overlay/animacao. O efeito continua logico pela area.
        return

    def draw_domain_cutscene(self):
        # Apenas texto curto: muito mais leve que criar superficies alpha gigantes por frame.
        if self.domain_message_timer <= 0:
            return
        draw_text("EXPANSAO DE DOMINIO", FONT_L, WHITE, (W/2, H*0.25), True)
        draw_text(self.domain_name, FONT_M, self.player.color, (W/2, H*0.31), True)
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
        else:
            draw_text(f"ONDA {self.wave}", FONT_M, WHITE, (x, sy+S(82)))
        draw_text(f"KOs {self.kills}   $ {self.run_coins}", FONT_S, GRAY, (x, sy+S(130)))

        if self.combo > 0:
            draw_text(f"COMBO x{1 + self.combo*0.08:.1f}", FONT_M, YELLOW, (W/2, S(86)), True)

        # Expansao de Dominio no topo direito
        uw = min(S(700), int(W * 0.31))
        ux, uy, uh = W-SAFE-uw, S(35), S(28)
        pygame.draw.rect(SCREEN, DARK, (ux, uy, uw, uh), border_radius=S(10))
        if p.character == "Glonk":
            draw_text("DOMINIO: Glonk nao chegou tao longe", FONT_S, GRAY, (ux, uy+S(42)))
        elif self.domain_active:
            ratio = clamp(self.domain_timer / max(0.01, self.domain_duration), 0, 1)
            pygame.draw.rect(SCREEN, p.color, (ux, uy, uw*ratio, uh), border_radius=S(10))
            draw_text(f"DOMINIO ATIVO {self.domain_timer:.1f}s - {p.domain_name}", FONT_S, WHITE, (ux, uy+S(42)))
        else:
            pygame.draw.rect(SCREEN, PURPLE, (ux, uy, uw*(self.domain_charge/100), uh), border_radius=S(10))
            draw_text(f"DOMINIO {int(self.domain_charge)}% - {p.domain_name}", FONT_S, WHITE, (ux, uy+S(42)))

        if self.event_name:
            draw_text("EVENTO: " + self.event_name, FONT_S, PINK, (W/2, S(165)), True)

        if self.achievement_timer > 0:
            r = pygame.Rect(W/2-S(250), S(205), S(500), S(70))
            pygame.draw.rect(SCREEN, PANEL2, r, border_radius=S(18))
            draw_text("CONQUISTA: " + self.achievement, FONT_S, YELLOW, r.center, True)

    def draw_controls(self):
        for d in ("left", "right", "up", "down"):
            pygame.draw.rect(SCREEN, PANEL2, self.buttons[d], border_radius=S(22))
            label = {"left":"<", "right":">", "up":"^", "down":"v"}[d]
            draw_text(label, FONT_L, WHITE, self.buttons[d].center, True)
        circle_button(self.buttons["attack"], "ATK", RED)
        circle_button(self.buttons["dash"], "DASH", CYAN)
        circle_button(self.buttons["parry"], "PARRY", YELLOW)
        dom_color = PURPLE if self.domain_charge >= 100 and self.player.character != "Glonk" else PANEL2
        circle_button(self.buttons["domain"], "DOM", dom_color)
        pygame.draw.rect(SCREEN, PANEL2, self.buttons["pause"], border_radius=S(16))
        draw_text("PAUSE", FONT_S, WHITE, self.buttons["pause"].center, True)
        if self.mode == "afk":
            colors = {"DUMMY": PANEL2, "TIRO": PINK, "DOM": PURPLE, "UP": BLUE}
            for label, rect in self.afk_buttons.items():
                pygame.draw.rect(SCREEN, colors[label], rect, border_radius=S(12))
                draw_text(label, FONT_S, WHITE, rect.center, True)

    def draw_playing(self):
        self.draw_bg()
        offset = self.camera_offset()
        self.draw_domain_zone(offset)
        for d in self.drops:
            d.draw(offset)
        for p in self.projectiles:
            p.draw(offset)
        for summon in self.summons:
            summon.draw(offset)
        for e in self.enemies:
            e.draw(offset)
        for p in self.particles:
            p.draw(offset)
        self.player.draw(offset, self)
        for d in self.damage_texts:
            d.draw(offset)
        self.draw_hud()
        self.draw_controls()

        if self.wave_banner > 0 and self.mode == "arena":
            draw_text("BOSS" if self.wave % 5 == 0 else f"ONDA {self.wave}", FONT_XL, WHITE, (W/2, H*0.36), True)
        if self.unlock_notice_timer > 0:
            draw_text(self.unlock_notice, FONT_L, PURPLE, (W/2,H*0.20), True)
        if self.synergy_timer > 0:
            draw_text("《 SINERGIA DESPERTADA 》", FONT_M, YELLOW, (W/2,H*0.27), True)
            draw_text(self.synergy_name, FONT_L, WHITE, (W/2,H*0.33), True)
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
        SCREEN.blit(title_img, title_img.get_rect(center=(W/2, H*0.16)))
        draw_text(subtitle, FONT_FANCY_S, GRAY, (W/2, H*0.235), True)

        btn_w = min(S(650), W - SAFE*4)
        start = pygame.Rect(W/2-btn_w/2, H*0.35, btn_w, S(110))
        afk = pygame.Rect(W/2-btn_w/2, H*0.47, btn_w, S(96))
        shop = pygame.Rect(W/2-btn_w/2, H*0.58, btn_w, S(96))
        pygame.draw.rect(SCREEN, RED, start, border_radius=S(25))
        pygame.draw.rect(SCREEN, CYAN, afk, border_radius=S(25))
        pygame.draw.rect(SCREEN, PANEL2, shop, border_radius=S(25))
        draw_text("JOGAR", FONT_L, WHITE, start.center, True)
        draw_text("ZONA AFK / TESTES", FONT_M, DARK, afk.center, True)
        draw_text("LOJA PERMANENTE", FONT_M, WHITE, shop.center, True)

        # Audio: controles persistentes, tambem presentes no pause.
        aw, ah, ag = S(310), S(64), S(24)
        sfx_btn = pygame.Rect(W/2-aw-ag//2, int(H*0.675), aw, ah)
        music_btn = pygame.Rect(W/2+ag//2, int(H*0.675), aw, ah)
        pygame.draw.rect(SCREEN, GREEN if AUDIO.sfx_on else PANEL2, sfx_btn, border_radius=S(16))
        pygame.draw.rect(SCREEN, GREEN if AUDIO.music_on else PANEL2, music_btn, border_radius=S(16))
        draw_text("EFEITOS: " + ("ON" if AUDIO.sfx_on else "OFF"), FONT_S, DARK if AUDIO.sfx_on else WHITE, sfx_btn.center, True)
        draw_text("MUSICA: " + ("ON" if AUDIO.music_on else "OFF"), FONT_S, DARK if AUDIO.music_on else WHITE, music_btn.center, True)
        self.menu_sfx_rect = sfx_btn
        self.menu_music_rect = music_btn

        draw_text(f"MOEDAS: {SAVE['coins']}   |   MELHOR ONDA: {SAVE['best_wave']}   |   RECORDE KOs: {SAVE['best_kills']}", FONT_S, GRAY, (W/2, H*0.77), True)
        draw_text("HP + Estamina | Builds, sinergias e Expansao de Dominio", FONT_S, CYAN, (W/2, H*0.835), True)
        if SAVE.get("kayk_unlocked", False):
            draw_text("KAYK DESBLOQUEADO", FONT_S, PURPLE, (W/2, H*0.875), True)
        draw_text("Teclado: WASD | ESPACO atacar | SHIFT dash | E parry | Q dominio", FONT_S, GRAY, (W/2, H*0.93), True)
        self.menu_start_rect = start
        self.menu_afk_rect = afk
        self.menu_shop_rect = shop

    def draw_character_select(self):
        SCREEN.fill(BG)
        draw_text("ESCOLHA SEU PERSONAGEM", FONT_L, WHITE, (W/2, S(82)), True)
        mode_text = "PARTIDA" if self.selection_target == "arena" else "ZONA AFK"
        draw_text(mode_text, FONT_S, CYAN, (W/2, S(138)), True)

        names = ["Ana", "Kevyn", "Ycaro", "Kayk", "Glonk"]
        gap = S(20)
        card_w = int((W - SAFE*2 - gap*4) / 5)
        card_h = min(S(670), int(H*0.67))
        y = S(190)
        self.character_rects = []
        for i, name in enumerate(names):
            cfg = CHARACTER_CONFIG[name]
            unlocked = name != "Kayk" or SAVE.get("kayk_unlocked", False)
            x = SAFE + i*(card_w+gap)
            r = pygame.Rect(x, y, card_w, card_h)
            border = cfg["color"] if unlocked else GRAY
            pygame.draw.rect(SCREEN, PANEL, r, border_radius=S(24))
            pygame.draw.rect(SCREEN, border, r, width=S(5), border_radius=S(24))
            draw_text(name.upper(), FONT_M, border, (r.centerx, r.y+S(55)), True)
            draw_text(cfg["weapon_name"], FONT_S, WHITE if unlocked else GRAY, (r.centerx, r.y+S(110)), True)

            parts = [x.strip() for x in cfg["desc"].split("|")]
            if name == "Glonk":
                draw_text("não faz nada e morre", FONT_S, GRAY, (r.centerx, r.y+S(175)), True)
            else:
                for j, part in enumerate(parts[:3]):
                    draw_text(part, FONT_S, GRAY, (r.centerx, r.y+S(165+j*38)), True)

            draw_text(f"HP: {cfg['hp']}", FONT_S, RED, (r.centerx, r.y+S(300)), True)
            draw_text(f"STA: {cfg['stamina']}", FONT_S, CYAN, (r.centerx, r.y+S(342)), True)
            draw_text("DOMINIO", FONT_S, PURPLE if unlocked else GRAY, (r.centerx, r.y+S(400)), True)
            draw_text(cfg["domain"], FONT_S, PURPLE if unlocked else GRAY, (r.centerx, r.y+S(438)), True)

            choose = pygame.Rect(r.x+S(24), r.bottom-S(90), r.w-S(48), S(62))
            if unlocked:
                pygame.draw.rect(SCREEN, cfg["color"], choose, border_radius=S(16))
                draw_text("ESCOLHER", FONT_S, DARK, choose.center, True)
            else:
                pygame.draw.rect(SCREEN, PANEL2, choose, border_radius=S(16))
                draw_text("BLOQUEADO", FONT_S, GRAY, choose.center, True)
                draw_text("DERROTE O PAI DO KAYK", FONT_S, YELLOW, (r.centerx, r.bottom-S(122)), True)
            self.character_rects.append((r, name, unlocked))

        back = pygame.Rect(SAFE, H-S(92), S(230), S(62))
        pygame.draw.rect(SCREEN, PANEL2, back, border_radius=S(16))
        draw_text("VOLTAR", FONT_S, WHITE, back.center, True)
        self.character_back_rect = back


    def draw_shop(self):
        SCREEN.fill(BG)
        draw_text("LOJA PERMANENTE", FONT_L, WHITE, (W/2, S(100)), True)
        draw_text(f"MOEDAS: {SAVE['coins']}", FONT_M, ORANGE, (W/2, S(165)), True)
        items = [
            ("vitality_level", "VITALIDADE", "+8 HP e +6 Estamina por nivel", 45),
            ("damage_level", "DANO", "+8% dano inicial por nivel", 55),
            ("speed_level", "VELOCIDADE", "+3% velocidade por nivel", 40),
        ]
        self.shop_rects = []
        y = S(280)
        for key, name, desc, base in items:
            lvl = SAVE[key]
            cost = base + lvl * 35
            r = pygame.Rect(S(80), y, W-S(160), S(175))
            pygame.draw.rect(SCREEN, PANEL, r, border_radius=S(24))
            draw_text(f"{name}  LV.{lvl}", FONT_M, WHITE, (r.x+S(30), r.y+S(25)))
            draw_text(desc, FONT_S, GRAY, (r.x+S(30), r.y+S(82)))
            buy = pygame.Rect(r.right-S(225), r.y+S(45), S(185), S(80))
            pygame.draw.rect(SCREEN, ORANGE if SAVE["coins"] >= cost else PANEL2, buy, border_radius=S(18))
            draw_text(f"{cost} $", FONT_M, WHITE, buy.center, True)
            self.shop_rects.append((buy, key, cost))
            y += S(210)
        back = pygame.Rect(S(70), H-S(150), S(260), S(80))
        pygame.draw.rect(SCREEN, PANEL2, back, border_radius=S(18))
        draw_text("VOLTAR", FONT_M, WHITE, back.center, True)
        self.shop_back_rect = back

    def draw_upgrade(self):
        SCREEN.fill(BG)
        draw_text("ONDA CONCLUIDA", FONT_L, GREEN, (W/2, S(110)), True)
        draw_text("ESCOLHA 1 MELHORIA", FONT_M, WHITE, (W/2, S(175)), True)
        if self.unlock_notice_timer > 0:
            draw_text(self.unlock_notice, FONT_M, PURPLE, (W-S(310), S(115)), True)
        rarity_color = {"common": GRAY, "rare": BLUE, "epic": PURPLE, "legendary": YELLOW, "cursed": RED}
        rarity_name = {"common": "COMUM", "rare": "RARO", "epic": "EPICO", "legendary": "LENDARIO", "cursed": "AMALDICOADO"}
        self.upgrade_rects = []
        y = S(280)
        for card in self.upgrade_cards:
            rarity, name, desc, key = card
            r = pygame.Rect(S(65), y, W-S(130), S(235))
            pygame.draw.rect(SCREEN, PANEL, r, border_radius=S(26))
            pygame.draw.rect(SCREEN, rarity_color[rarity], r, width=S(5), border_radius=S(26))
            draw_text(rarity_name[rarity], FONT_S, rarity_color[rarity], (r.x+S(28), r.y+S(22)))
            draw_text(name, FONT_M, WHITE, (r.x+S(28), r.y+S(70)))
            draw_text(desc, FONT_S, GRAY, (r.x+S(28), r.y+S(135)))
            draw_text("TOQUE PARA ESCOLHER", FONT_S, rarity_color[rarity], (r.x+S(28), r.y+S(185)))
            self.upgrade_rects.append((r, card))
            y += S(270)

    def draw_death(self):
        SCREEN.fill((24, 10, 14))
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
        y = H*0.31
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
        self.attack_held = False
        for key in self.move_touch:
            self.move_touch[key] = False
        self.active_fingers.clear()

    def draw_paused(self):
        # Mostra o frame congelado por baixo e um menu simples.
        self.draw_playing()
        overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 185))
        SCREEN.blit(overlay, (0, 0))
        draw_text("PAUSADO", FONT_XL, WHITE, (W/2, H*0.30), True)
        bw, bh = S(520), S(92)
        resume = pygame.Rect(W/2-bw/2, H*0.43, bw, bh)
        menu = pygame.Rect(W/2-bw/2, H*0.55, bw, bh)
        pygame.draw.rect(SCREEN, CYAN, resume, border_radius=S(22))
        pygame.draw.rect(SCREEN, PANEL2, menu, border_radius=S(22))
        draw_text("CONTINUAR", FONT_M, DARK, resume.center, True)
        draw_text("VOLTAR AO MENU", FONT_M, WHITE, menu.center, True)

        aw, ah, ag = S(250), S(72), S(20)
        sfx_btn = pygame.Rect(W/2-aw-ag//2, int(H*0.69), aw, ah)
        music_btn = pygame.Rect(W/2+ag//2, int(H*0.69), aw, ah)
        pygame.draw.rect(SCREEN, GREEN if AUDIO.sfx_on else PANEL2, sfx_btn, border_radius=S(16))
        pygame.draw.rect(SCREEN, GREEN if AUDIO.music_on else PANEL2, music_btn, border_radius=S(16))
        draw_text("SFX " + ("ON" if AUDIO.sfx_on else "OFF"), FONT_S, DARK if AUDIO.sfx_on else WHITE, sfx_btn.center, True)
        draw_text("MUSICA " + ("ON" if AUDIO.music_on else "OFF"), FONT_S, DARK if AUDIO.music_on else WHITE, music_btn.center, True)
        self.pause_resume_rect = resume
        self.pause_menu_rect = menu
        self.pause_sfx_rect = sfx_btn
        self.pause_music_rect = music_btn

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
        elif self.state == "shop":
            self.draw_shop()
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
        elif self.state == "character_select":
            if self.character_back_rect.collidepoint(pos):
                self.state = "menu"
            else:
                for r, name, unlocked in self.character_rects:
                    if r.collidepoint(pos) and unlocked:
                        AUDIO.play("click", 0.75)
                        self.selected_character = name
                        if self.selection_target == "afk":
                            self.start_afk(name)
                        else:
                            self.reset_run(name)
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
            elif self.pause_menu_rect.collidepoint(pos):
                AUDIO.play("click", 0.65); self.state = "menu"
        elif self.state == "glonk_death":
            if self.glonk_menu_rect.collidepoint(pos):
                self.state = "menu"
        elif self.state == "shop":
            if self.shop_back_rect.collidepoint(pos):
                self.state = "menu"
            else:
                for r, key, cost in self.shop_rects:
                    if r.collidepoint(pos) and SAVE["coins"] >= cost:
                        AUDIO.play("upgrade", 0.75)
                        SAVE["coins"] -= cost
                        SAVE[key] += 1
                        save_data(SAVE)
                        break
        elif self.state == "upgrade":
            for r, card in self.upgrade_rects:
                if r.collidepoint(pos):
                    self.apply_upgrade(card)
                    break
        elif self.state == "death":
            if self.death_retry_rect.collidepoint(pos):
                self.reset_run(self.selected_character)
            elif self.death_menu_rect.collidepoint(pos):
                self.state = "menu"


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
                if game.state == "playing":
                    if event.key == pygame.K_SPACE:
                        game.player.attack(game)
                    elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        game.player.dash(game, game.get_move_dir())
                    elif event.key == pygame.K_e:
                        game.player.parry(game)
                    elif event.key == pygame.K_q:
                        game.player.expand_domain(game)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                # Em Pygame 2, toque pode gerar FINGER + MOUSE sintético.
                # Ignoramos o mouse sintético para não ativar botões duas vezes.
                if not getattr(event, "touch", False):
                    if game.state == "playing":
                        game.handle_touch_down(to_game_pos(event.pos))
                    else:
                        game.click_ui(to_game_pos(event.pos))
            elif event.type == pygame.MOUSEBUTTONUP:
                if not getattr(event, "touch", False):
                    game.handle_touch_up(to_game_pos(event.pos))
            elif event.type == pygame.FINGERDOWN:
                physical = (event.x * PHYS_W, event.y * PHYS_H)
                pos = to_game_pos(physical)
                if game.state == "playing":
                    game.handle_touch_down(pos, event.finger_id)
                else:
                    game.click_ui(pos)
            elif event.type == pygame.FINGERUP:
                physical = (event.x * PHYS_W, event.y * PHYS_H)
                game.handle_touch_up(to_game_pos(physical), event.finger_id)

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
