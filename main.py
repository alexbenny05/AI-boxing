import pygame
import cv2
import mediapipe as mp
import numpy as np
import time
import random
from mediapipe.tasks.python import vision
from mediapipe.tasks.python import BaseOptions

# -------------------------------
# INIT PYGAME
# -------------------------------
pygame.init()
pygame.mixer.init()

WIDTH, HEIGHT = 1000, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("AI Street Fighter (Gesture Controlled)")
clock = pygame.time.Clock()

# -------------------------------
# SOUNDS (OPTIONAL)
# -------------------------------
def safe_sound(path):
    try:
        return pygame.mixer.Sound(path)
    except:
        return None

punch_sound = safe_sound("punch.wav")
hit_sound = safe_sound("hit.wav")
ko_sound = safe_sound("ko.wav")
enemy_punch_sound = safe_sound("enemypunch.wav")

# -------------------------------
# FONTS
# -------------------------------
font = pygame.font.SysFont("Arial", 35, bold=True)
big_font = pygame.font.SysFont("Arial", 90, bold=True)
mid_font = pygame.font.SysFont("Arial", 60, bold=True)

# -------------------------------
# MEDIAPIPE HAND TRACKER
# -------------------------------
model_path = "hand_landmarker.task"

options = vision.HandLandmarkerOptions(
    base_options=BaseOptions(model_asset_path=model_path),
    running_mode=vision.RunningMode.VIDEO,
    num_hands=2
)

detector = vision.HandLandmarker.create_from_options(options)

cap = cv2.VideoCapture(0)
timestamp = 0

# -------------------------------
# GAME VARIABLES
# -------------------------------
player_hp = 100
enemy_hp = 100

player_state = "idle"
enemy_state = "idle"

punch_cooldown = 0.4
last_punch_time = 0
punch_anim_time = 0

enemy_attack_cooldown = 1.7
enemy_last_attack = time.time()
enemy_attack_duration = 0.35
enemy_attack_start = 0

hit_effect_time = 0
player_hit_time = 0

combo = 0
combo_timer = 0

game_over = False
winner = ""

round_start_time = time.time()
intro_start_time = time.time()

# Wrist tracking
prev_left = None
prev_right = None
punch_threshold = 60

# Positions
player_x, player_y = 220, 380
enemy_x, enemy_y = 780, 380

# FX
screen_shake_time = 0
sparks = []

# -------------------------------
# FUNCTIONS
# -------------------------------
def draw_health_bar(x, y, hp, max_hp, color):
    bar_width = 300
    bar_height = 30
    fill = int((hp / max_hp) * bar_width)

    pygame.draw.rect(screen, (40, 40, 40), (x, y, bar_width, bar_height))
    pygame.draw.rect(screen, color, (x, y, fill, bar_height))
    pygame.draw.rect(screen, (255, 255, 255), (x, y, bar_width, bar_height), 3)


def create_hit_sparks(x, y):
    global sparks
    for _ in range(15):
        sparks.append({
            "x": x,
            "y": y,
            "vx": random.uniform(-5, 5),
            "vy": random.uniform(-5, 5),
            "life": random.randint(10, 18)
        })


def draw_sparks():
    global sparks
    for s in sparks:
        pygame.draw.circle(screen, (255, 255, 0), (int(s["x"]), int(s["y"])), 4)
        pygame.draw.circle(screen, (255, 120, 0), (int(s["x"]), int(s["y"])), 2)

        s["x"] += s["vx"]
        s["y"] += s["vy"]
        s["life"] -= 1

    sparks = [s for s in sparks if s["life"] > 0]


def reset_game():
    global player_hp, enemy_hp, combo, game_over, winner
    global round_start_time, prev_left, prev_right
    global enemy_last_attack, intro_start_time
    global player_state, enemy_state

    player_hp = 100
    enemy_hp = 100
    combo = 0
    game_over = False
    winner = ""
    round_start_time = time.time()
    intro_start_time = time.time()

    prev_left = None
    prev_right = None
    enemy_last_attack = time.time()

    player_state = "idle"
    enemy_state = "idle"


# -------------------------------
# STREET FIGHTER STYLE CHARACTER DRAWING
# -------------------------------
def draw_fighter(x, y, facing="right", state="idle", color=(50, 120, 255), shake=(0, 0)):
    """
    Draws an arcade-style fighter using shapes.
    x,y = feet position
    """

    sx, sy = shake

    # Idle bounce
    bounce = int(6 * np.sin(time.time() * 6))

    if state == "hit":
        bounce += 5

    # Body sizes
    head_r = 22
    body_w = 50
    body_h = 90

    # Feet offset
    y = y + bounce

    # Main body coordinates
    head_x = x
    head_y = y - 150

    body_x = x - body_w // 2
    body_y = y - 130

    # Outline function
    def outline_circle(pos, radius):
        pygame.draw.circle(screen, (0, 0, 0), pos, radius + 4)
        pygame.draw.circle(screen, (255, 220, 170), pos, radius)

    def outline_rect(rect, fill):
        pygame.draw.rect(screen, (0, 0, 0), rect.inflate(8, 8), border_radius=12)
        pygame.draw.rect(screen, fill, rect, border_radius=12)

    # Head
    outline_circle((head_x + sx, head_y + sy), head_r)

    # Hair (Street Fighter vibe)
    pygame.draw.polygon(screen, (20, 20, 20), [
        (head_x - 20 + sx, head_y - 15 + sy),
        (head_x + 20 + sx, head_y - 15 + sy),
        (head_x + 10 + sx, head_y - 35 + sy),
        (head_x - 10 + sx, head_y - 35 + sy)
    ])

    # Body
    outline_rect(pygame.Rect(body_x + sx, body_y + sy, body_w, body_h), color)

    # Belt
    pygame.draw.rect(screen, (0, 0, 0), (body_x + sx, body_y + 55 + sy, body_w, 12))
    pygame.draw.rect(screen, (255, 255, 0), (body_x + 10 + sx, body_y + 57 + sy, body_w - 20, 8))

    # Legs
    leg_color = (30, 30, 30)
    pygame.draw.line(screen, (0, 0, 0), (x - 15 + sx, y - 40 + sy), (x - 30 + sx, y + sy), 10)
    pygame.draw.line(screen, leg_color, (x - 15 + sx, y - 40 + sy), (x - 30 + sx, y + sy), 6)

    pygame.draw.line(screen, (0, 0, 0), (x + 15 + sx, y - 40 + sy), (x + 30 + sx, y + sy), 10)
    pygame.draw.line(screen, leg_color, (x + 15 + sx, y - 40 + sy), (x + 30 + sx, y + sy), 6)

    # Shoes
    pygame.draw.ellipse(screen, (0, 0, 0), (x - 42 + sx, y - 10 + sy, 30, 15))
    pygame.draw.ellipse(screen, (255, 255, 255), (x - 40 + sx, y - 9 + sy, 26, 12))

    pygame.draw.ellipse(screen, (0, 0, 0), (x + 12 + sx, y - 10 + sy, 30, 15))
    pygame.draw.ellipse(screen, (255, 255, 255), (x + 14 + sx, y - 9 + sy, 26, 12))

    # Arms + Gloves (state based)
    glove_color = (200, 0, 0) if color == (50, 120, 255) else (0, 100, 255)

    if facing == "right":
        punch_dir = 1
    else:
        punch_dir = -1

    # Default arm positions
    arm_y = body_y + 30
    left_hand = (x - 50, arm_y + 20)
    right_hand = (x + 50, arm_y + 20)

    if state == "block":
        # Both hands up
        left_hand = (x - 20, head_y + 10)
        right_hand = (x + 20, head_y + 10)

    if state == "punch":
        # Extend one arm
        right_hand = (x + 120 * punch_dir, arm_y + 10)

        # Punch trail glow
        pygame.draw.ellipse(screen, (255, 255, 0),
                            (right_hand[0] - 40 + sx, right_hand[1] - 20 + sy, 80, 40))

    if state == "hit":
        # Arms loose
        left_hand = (x - 60, arm_y + 40)
        right_hand = (x + 60, arm_y + 40)

    # Arm lines (outline)
    pygame.draw.line(screen, (0, 0, 0), (x - 20 + sx, arm_y + sy), (left_hand[0] + sx, left_hand[1] + sy), 12)
    pygame.draw.line(screen, (255, 220, 170), (x - 20 + sx, arm_y + sy), (left_hand[0] + sx, left_hand[1] + sy), 7)

    pygame.draw.line(screen, (0, 0, 0), (x + 20 + sx, arm_y + sy), (right_hand[0] + sx, right_hand[1] + sy), 12)
    pygame.draw.line(screen, (255, 220, 170), (x + 20 + sx, arm_y + sy), (right_hand[0] + sx, right_hand[1] + sy), 7)

    # Gloves
    pygame.draw.circle(screen, (0, 0, 0), (left_hand[0] + sx, left_hand[1] + sy), 18)
    pygame.draw.circle(screen, glove_color, (left_hand[0] + sx, left_hand[1] + sy), 14)

    pygame.draw.circle(screen, (0, 0, 0), (right_hand[0] + sx, right_hand[1] + sy), 18)
    pygame.draw.circle(screen, glove_color, (right_hand[0] + sx, right_hand[1] + sy), 14)

    # Chest Highlight (adds vibe)
    pygame.draw.rect(screen, (255, 255, 255), (body_x + 8 + sx, body_y + 15 + sy, 10, 40))
    pygame.draw.rect(screen, (255, 255, 255), (body_x + 32 + sx, body_y + 15 + sy, 10, 40))


def draw_background():
    # Simple street-fighter vibe stage
    screen.fill((20, 20, 30))

    # Floor
    pygame.draw.rect(screen, (40, 40, 60), (0, 420, WIDTH, 200))
    pygame.draw.rect(screen, (70, 70, 100), (0, 470, WIDTH, 150))

    # Stage lights
    for i in range(10):
        pygame.draw.circle(screen, (255, 255, 80), (100 + i * 90, 80), 8)

    # Crowd silhouettes
    for i in range(60):
        cx = i * 18
        cy = 360 + random.randint(-5, 5)
        pygame.draw.rect(screen, (10, 10, 10), (cx, cy, 12, 40))

    # Neon board
    pygame.draw.rect(screen, (0, 0, 0), (250, 150, 500, 80))
    pygame.draw.rect(screen, (255, 0, 0), (255, 155, 490, 70), 4)
    text = font.render("AI EXPO FIGHT NIGHT", True, (255, 255, 0))
    screen.blit(text, (320, 170))


# -------------------------------
# MAIN LOOP
# -------------------------------
running = True
while running:
    clock.tick(60)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                reset_game()

    # -------------------------------
    # CAMERA + HAND DETECTION
    # -------------------------------
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)
    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

    timestamp += 16
    result = detector.detect_for_video(mp_image, timestamp)

    left_punch = False
    right_punch = False
    block = False

    if result.hand_landmarks and not game_over:
        wrists = []

        for hand in result.hand_landmarks:
            wrist = hand[0]
            wx, wy = int(wrist.x * WIDTH), int(wrist.y * HEIGHT)
            wrists.append((wx, wy))

        wrists.sort(key=lambda x: x[0])

        left = wrists[0] if len(wrists) >= 1 else None
        right = wrists[1] if len(wrists) == 2 else None

        if left and prev_left:
            dist = np.sqrt((left[0] - prev_left[0])**2 + (left[1] - prev_left[1])**2)
            if dist > punch_threshold:
                left_punch = True

        if right and prev_right:
            dist = np.sqrt((right[0] - prev_right[0])**2 + (right[1] - prev_right[1])**2)
            if dist > punch_threshold:
                right_punch = True

        prev_left = left
        prev_right = right

        # Block detection
        if left and right:
            if left[1] < HEIGHT // 2 and right[1] < HEIGHT // 2:
                block = True

    # -------------------------------
    # PLAYER ATTACK LOGIC
    # -------------------------------
    current_time = time.time()

    if not game_over:
        if block:
            player_state = "block"

        elif (left_punch or right_punch) and (current_time - last_punch_time > punch_cooldown):
            player_state = "punch"
            last_punch_time = current_time
            punch_anim_time = current_time

            damage = 10
            enemy_hp -= damage

            if punch_sound:
                punch_sound.play()
            if hit_sound:
                hit_sound.play()

            enemy_state = "hit"
            hit_effect_time = current_time
            screen_shake_time = current_time

            create_hit_sparks(enemy_x - 50, enemy_y - 140)

            if current_time - combo_timer < 1.2:
                combo += 1
            else:
                combo = 1
            combo_timer = current_time

            if enemy_hp <= 0:
                enemy_hp = 0
                game_over = True
                winner = "PLAYER"
                enemy_state = "ko"
                if ko_sound:
                    ko_sound.play()

        else:
            player_state = "idle"

    if player_state == "punch" and current_time - punch_anim_time > 0.25:
        player_state = "idle"

    if enemy_state == "hit" and current_time - hit_effect_time > 0.3:
        enemy_state = "idle"

    if player_state == "hit" and current_time - player_hit_time > 0.3:
        player_state = "idle"

    # -------------------------------
    # ENEMY AI ATTACK LOGIC
    # -------------------------------
    if not game_over:
        if current_time - enemy_last_attack > enemy_attack_cooldown:
            enemy_last_attack = current_time
            enemy_attack_start = current_time
            enemy_state = "punch"

            if enemy_punch_sound:
                enemy_punch_sound.play()

            if not block:
                player_hp -= random.randint(8, 15)
                player_state = "hit"
                player_hit_time = current_time

                if hit_sound:
                    hit_sound.play()

                screen_shake_time = current_time
                create_hit_sparks(player_x + 40, player_y - 140)

                if player_hp <= 0:
                    player_hp = 0
                    game_over = True
                    winner = "ENEMY"
                    if ko_sound:
                        ko_sound.play()

    if enemy_state == "punch" and current_time - enemy_attack_start > enemy_attack_duration:
        if not game_over:
            enemy_state = "idle"

    # -------------------------------
    # SCREEN SHAKE
    # -------------------------------
    if current_time - screen_shake_time < 0.2:
        shake_x = random.randint(-10, 10)
        shake_y = random.randint(-10, 10)
    else:
        shake_x, shake_y = 0, 0

    # -------------------------------
    # DRAW EVERYTHING
    # -------------------------------
    draw_background()

    # Health bars
    player_color = (0, 255, 0)
    enemy_color = (255, 0, 0)

    if current_time - player_hit_time < 0.2:
        player_color = (255, 80, 80)

    if current_time - hit_effect_time < 0.2:
        enemy_color = (255, 255, 0)

    draw_health_bar(50, 40, player_hp, 100, player_color)
    draw_health_bar(WIDTH - 350, 40, enemy_hp, 100, enemy_color)

    # Timer
    timer = max(0, 60 - int(current_time - round_start_time))
    timer_text = font.render(str(timer), True, (255, 255, 255))
    screen.blit(timer_text, (WIDTH // 2 - 20, 40))

    # Fighters
    if enemy_state == "ko":
        # KO fall down effect
        pygame.draw.rect(screen, (0, 0, 0), (enemy_x - 90 + shake_x, enemy_y - 50 + shake_y, 180, 40))
        pygame.draw.rect(screen, (255, 0, 0), (enemy_x - 85 + shake_x, enemy_y - 45 + shake_y, 170, 30))
    else:
        draw_fighter(enemy_x + shake_x, enemy_y + shake_y,
                     facing="left", state=enemy_state, color=(255, 70, 70))

    if player_state != "ko":
        draw_fighter(player_x + shake_x, player_y + shake_y,
                     facing="right", state=player_state, color=(50, 120, 255))

    # Sparks
    draw_sparks()

    # Combo
    if combo >= 2 and not game_over:
        combo_text = font.render(f"{combo} HIT COMBO!", True, (255, 255, 0))
        screen.blit(combo_text, (WIDTH // 2 - 140, 120))

    # Intro text
    intro_elapsed = current_time - intro_start_time
    if intro_elapsed < 1.5:
        round_text = mid_font.render("ROUND 1", True, (255, 255, 0))
        screen.blit(round_text, (WIDTH // 2 - 140, HEIGHT // 2 - 160))

    elif intro_elapsed < 2.8:
        fight_text = big_font.render("FIGHT!", True, (255, 0, 0))
        screen.blit(fight_text, (WIDTH // 2 - 180, HEIGHT // 2 - 140))

    # Winner screen
    if game_over:
        ko_text = big_font.render("K.O!", True, (255, 255, 0))
        screen.blit(ko_text, (WIDTH // 2 - 130, HEIGHT // 2 - 140))

        win_text = font.render(f"{winner} WINS!", True, (255, 255, 255))
        screen.blit(win_text, (WIDTH // 2 - 120, HEIGHT // 2 - 40))

        restart_text = font.render("Press R to Restart", True, (255, 255, 255))
        screen.blit(restart_text, (WIDTH // 2 - 170, HEIGHT // 2 + 40))

    pygame.display.update()

cap.release()
pygame.quit()