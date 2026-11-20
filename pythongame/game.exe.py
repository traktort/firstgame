import math
import os
import random
import pygame as pg

pg.init()

# Window settings
screen_width = 1000
screen_height = 800
fps = 60

screen = pg.display.set_mode((screen_width, screen_height))
pg.display.set_caption("Asteroids")
clock = pg.time.Clock()

# Player
try:
    player_original = pg.image.load("ship.png").convert_alpha()
    player_original = pg.transform.smoothscale(player_original, (74, 74))
except (FileNotFoundError, OSError, pg.error):
    player_original = pg.Surface((50, 50), pg.SRCALPHA)
    pg.draw.polygon(player_original, (220, 245, 255), [(25, 0), (48, 46), (25, 38), (2, 46)])

position = pg.Vector2(screen_width / 2, screen_height / 2)
velocity = pg.Vector2()
angle = 0
move_speed = 500
move_acceleration = 1200
player_radius = 28

# Shooting
bullets = []
shooting_cooldown = 0.0
shot_interval = 0.5
bullet_speed = 750
bullet_damage = 1

# Enemies
asteroids = []
enemy_ships = []
enemy_spawn_timer = 0.0
enemy_spawn_interval = 12.0
biggest_asteroid_radius = 64
smallest_asteroid_radius = 12
asteroid_speed = 150
max_asteroids = 20
spawn_interval = 0.6
spawn_timer = 0.0
boss = None
boss_bullets = []
next_boss_score = 30
boss_shot_interval = 1.15

# Game state
ship_health = 5
max_ship_health = 5
score = 0
palivo = 0
fuel_level = 0
fuel_requirement = 100
upgrade_menu = False
upgrade_level = 1

high_score_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "highscore.txt")
try:
    with open(high_score_file, "r", encoding="utf-8") as score_file:
        high_score = max(0, int(score_file.read().strip()))
except (FileNotFoundError, OSError, ValueError):
    high_score = 0

game_over = False
paused = False
start_screen = True
damage_cooldown = 0.0

# Visual
stars = [
    (random.randint(0, screen_width),
     random.randint(0, screen_height),
     random.choice([1, 1, 2, 2, 3]),
     random.randint(80, 220))
    for _ in range(170)
]
particles = []
trail = []

font_small = pg.font.Font(None, 26)
font = pg.font.Font(None, 34)
font_big = pg.font.Font(None, 64)

enemy_ship_image = pg.Surface((52, 52), pg.SRCALPHA)
pg.draw.polygon(enemy_ship_image, (235, 75, 95), [(26, 2), (48, 43), (26, 34), (4, 43)])
pg.draw.polygon(enemy_ship_image, (255, 195, 110), [(26, 10), (34, 34), (26, 29), (18, 34)])
boss_images = {}
for is_hit, color in ((False, (80, 120, 210)), (True, (255, 110, 110))):
    boss_image = pg.Surface((170, 170), pg.SRCALPHA)
    pg.draw.polygon(boss_image, color, [
        (85, 10), (112, 63), (155, 74), (128, 95),
        (112, 150), (85, 132), (58, 150), (42, 95),
        (15, 74), (58, 63)
    ])
    pg.draw.polygon(boss_image, (20, 28, 55), [
        (85, 30), (105, 72), (85, 112), (65, 72)
    ])
    pg.draw.circle(boss_image, (255, 210, 90), (85, 72), 12)
    pg.draw.circle(boss_image, (255, 245, 210), (85, 72), 5)
    boss_images[is_hit] = boss_image

player_rotation_cache = {}
enemy_rotation_cache = {}
boss_rotation_caches = {False: {}, True: {}}


def rotate_cached(image, cache, angle, angle_step=3):
    angle_key = round(angle / angle_step) * angle_step % 360
    if angle_key not in cache:
        cache[angle_key] = pg.transform.rotate(image, angle_key)
    return cache[angle_key]


class Bullet:
    def __init__(self, start_position, direction):
        self.position = start_position.copy()
        self.velocity = direction * bullet_speed
        self.radius = 5
        self.trail = []

    def update(self, dt):
        self.trail.append(self.position.copy())
        if len(self.trail) > 5:
            self.trail.pop(0)
        self.position += self.velocity * dt

    def draw(self, surface):
        for index, point in enumerate(self.trail):
            alpha = int(70 + index * 35)
            trail_radius = 2 + index // 2
            pg.draw.circle(surface, (255, 220, 100, alpha),
                           (round(point.x), round(point.y)), trail_radius)
        pg.draw.circle(surface, (255, 255, 220),
                       (round(self.position.x), round(self.position.y)), self.radius)
        pg.draw.circle(surface, (255, 190, 60),
                       (round(self.position.x), round(self.position.y)), self.radius + 3, 2)

    def outside_screen(self):
        return (self.position.x < -20 or self.position.x > screen_width + 20
                or self.position.y < -20 or self.position.y > screen_height + 20)


def create_asteroid():
    radius = random.randint(smallest_asteroid_radius, biggest_asteroid_radius)

    # Enemies do not spawn from the top or bottom.
    from_left = random.choice([True, False])
    if from_left:
        spawn = pg.Vector2(-radius - 10, random.randint(radius, screen_height - radius))
    else:
        spawn = pg.Vector2(screen_width + radius + 10, random.randint(radius, screen_height - radius))

    direction = position - spawn
    if direction.length_squared() > 0:
        direction = direction.normalize()

    # A blue asteroid appears about every third enemy.
    blue_smoke = random.random() < 0.32

    block_count = max(3, round(radius / 12))
    block_size = radius / block_count
    blocks = []
    for row in range(-block_count, block_count + 1):
        for column in range(-block_count, block_count + 1):
            normalized_x = column / block_count
            normalized_y = row / block_count
            if normalized_x * normalized_x + normalized_y * normalized_y <= 1.08:
                shade = random.choice(("light", "main", "dark"))
                blocks.append((column, row, shade))

    craters = [
        (random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5), random.uniform(0.08, 0.18))
        for _ in range(random.randint(2, 5))
    ]

    return {
        "position": spawn,
        "velocity": direction * random.randint(
            asteroid_speed - 30 + min(score * 2, 100) + fuel_level * 10,
            asteroid_speed + 50 + min(score * 2, 100) + fuel_level * 10
        ),
        "radius": radius,
        "blue_smoke": blue_smoke,
        "phase": random.uniform(0, math.tau),
        "rotation": random.uniform(0, math.tau),
        "rotation_speed": random.choice((-1, 1)) * random.uniform(0.25, 0.8),
        "image": create_asteroid_image(radius, block_size, blocks, craters, blue_smoke),
        "render_angle": None,
        "rendered_image": None
    }


def create_asteroid_image(radius, block_size, blocks, craters, blue_smoke):
    palette = ({
        "light": (105, 205, 255),
        "main": (35, 145, 230),
        "dark": (20, 85, 175)
    } if blue_smoke else {
        "light": (137, 140, 150),
        "main": (92, 98, 116),
        "dark": (70, 74, 88)
    })
    size = round(radius * 2 + block_size * 2 + 4)
    image = pg.Surface((size, size), pg.SRCALPHA)
    center = size // 2

    for column, row, shade in blocks:
        block_x = round(center + column * block_size - block_size / 2)
        block_y = round(center + row * block_size - block_size / 2)
        block_rect = pg.Rect(block_x, block_y, round(block_size + 1), round(block_size + 1))
        pg.draw.rect(image, palette[shade], block_rect)
        pg.draw.rect(image, (48, 53, 68), block_rect, 1)

    for dx, dy, crater_size in craters:
        crater_x = center + round(dx * radius)
        crater_y = center + round(dy * radius)
        crater_radius = round(crater_size * radius)
        pg.draw.rect(image, palette["dark"],
                     pg.Rect(crater_x - crater_radius, crater_y - crater_radius,
                             crater_radius * 2, crater_radius * 2),
                     border_radius=max(2, crater_radius // 2))
    return image


def create_enemy_ship():
    side = random.randrange(4)
    if side == 0:
        spawn = pg.Vector2(-30, random.randint(0, screen_height))
    elif side == 1:
        spawn = pg.Vector2(screen_width + 30, random.randint(0, screen_height))
    elif side == 2:
        spawn = pg.Vector2(random.randint(0, screen_width), -30)
    else:
        spawn = pg.Vector2(random.randint(0, screen_width), screen_height + 30)

    direction = position - spawn
    if direction.length_squared() > 0:
        direction.normalize_ip()

    return {
        "position": spawn,
        "velocity": direction * min(260, 125 + fuel_level * 12),
        "radius": 22,
        "health": 2 + fuel_level // 4
    }


def asteroid_outside_screen(asteroid):
    p = asteroid["position"]
    margin = asteroid["radius"] * 2
    return p.x < -margin or p.x > screen_width + margin or p.y < -margin or p.y > screen_height + margin


def create_explosion(p, blue=False):
    for _ in range(16):
        angle = random.uniform(0, math.tau)
        speed = random.uniform(40, 220)
        particles.append({
            "position": p.copy(),
            "velocity": pg.Vector2(math.cos(angle), math.sin(angle)) * speed,
            "life": random.uniform(0.35, 0.75),
            "max_life": 0.75,
            "blue": blue
        })


def draw_background(time_value):
    backgrounds = (
        ((5, 8, 28), (12, 22, 52), (9, 18, 43), (150, 190, 255)),
        ((24, 8, 30), (70, 20, 54), (42, 13, 39), (255, 155, 190)),
        ((5, 22, 30), (12, 62, 70), (8, 39, 52), (130, 235, 220)),
        ((25, 18, 6), (72, 49, 18), (44, 32, 12), (255, 215, 130)),
        ((12, 8, 34), (45, 28, 84), (25, 17, 58), (205, 165, 255))
    )
    background, glow_one, glow_two, star_tint = backgrounds[fuel_level % len(backgrounds)]
    screen.fill(background)

    pg.draw.circle(screen, glow_one, (screen_width - 130, 130), 230)
    pg.draw.circle(screen, glow_two, (120, screen_height - 110), 280)

    for x, y, radius, brightness in stars:
        flicker = int(brightness + 35 * math.sin(time_value * 2 + x))
        flicker = max(70, min(255, flicker))
        color = tuple(min(255, channel * flicker // 190) for channel in star_tint)
        pg.draw.circle(screen, color, (x, y), radius)


def draw_enemy_ship(enemy):
    direction = enemy["velocity"]
    rotation = -pg.Vector2(0, -1).angle_to(direction)
    rotated = rotate_cached(enemy_ship_image, enemy_rotation_cache, rotation, 5)
    screen.blit(rotated, rotated.get_rect(center=(round(enemy["position"].x),
                                                   round(enemy["position"].y))))


def draw_asteroid(asteroid, time_value):
    p = asteroid["position"]
    radius = asteroid["radius"]
    x = round(p.x)
    y = round(p.y)

    if asteroid["blue_smoke"]:
        pulse = 2 * math.sin(time_value * 4 + asteroid["phase"])
        pg.draw.circle(screen, (25, 95, 190),
                       (x, y), radius + 8 + round(pulse), 3)
    asteroid["rotation"] += asteroid["rotation_speed"] * (1 / 60)
    angle_key = round(math.degrees(asteroid["rotation"]) / 3) * 3 % 360
    if angle_key != asteroid["render_angle"]:
        asteroid["rendered_image"] = pg.transform.rotate(asteroid["image"], -angle_key)
        asteroid["render_angle"] = angle_key
    screen.blit(asteroid["rendered_image"],
                asteroid["rendered_image"].get_rect(center=(x, y)))


def spawn_boss():
    side = random.choice((-1, 1))
    spawn_x = 120 if side == -1 else screen_width - 120
    health = 24 + upgrade_level * 5 + fuel_level * 3
    return {
        "position": pg.Vector2(spawn_x, 150),
        "radius": 70,
        "health": health,
        "max_health": health,
        "phase": random.uniform(0, math.tau),
        "shot_timer": boss_shot_interval,
        "hit_flash": 0.0,
        "burst_timer": 3.5,
        "dash_timer": 5.0,
        "dash_velocity": pg.Vector2(),
        "level": 1
    }


def draw_boss(boss_value, time_value):
    p = boss_value["position"]
    x, y = round(p.x), round(p.y)
    health_ratio = boss_value["health"] / boss_value["max_health"]
    boss_value["level"] = 2 if health_ratio <= 0.5 else 1
    flash = boss_value["hit_flash"] > 0
    angle_to_player = pg.Vector2(0, -1).angle_to(position - p)
    ship_angle = -angle_to_player
    rotated = rotate_cached(boss_images[flash], boss_rotation_caches[flash], ship_angle)
    screen.blit(rotated, rotated.get_rect(center=(x, y)))

    bar_width = 180
    bar_rect = pg.Rect(round(x - bar_width / 2), y - 105, bar_width, 12)
    pg.draw.rect(screen, (35, 20, 30), bar_rect, border_radius=6)
    ratio = max(0.0, boss_value["health"] / boss_value["max_health"])
    pg.draw.rect(screen, (235, 70, 90),
                 pg.Rect(bar_rect.x, bar_rect.y, round(bar_width * ratio), bar_rect.height),
                 border_radius=6)
    phase_name = "SHIP BOSS - ENRAGED" if boss_value["level"] == 2 else "SHIP BOSS"
    name = font_small.render(phase_name, True,
                             (255, 120, 130) if boss_value["level"] == 2 else (255, 220, 220))
    screen.blit(name, name.get_rect(center=(x, y - 125)))


def draw_upgrade_menu():
    overlay = pg.Surface((screen_width, screen_height), pg.SRCALPHA)
    overlay.fill((3, 8, 24, 220))
    screen.blit(overlay, (0, 0))

    title = font_big.render("UPGRADE", True, (235, 245, 255))
    screen.blit(title, title.get_rect(center=(screen_width // 2, 210)))

    choices = [
        ("1", "Faster shooting", "Reduces delay between shots"),
        ("2", "Stronger ship", "Increases movement speed"),
        ("3", "Extra health", "Restores and increases health"),
        ("4", "Stronger bullets", "Every shot deals more damage"),
        ("5", "Reinforced hull", "Adds 3 maximum health"),
        ("6", "Fast projectiles", "Increases bullet speed")
    ]

    for index, (key, name, description) in enumerate(choices):
        y = 270 + index * 78
        rect = pg.Rect(220, y, 560, 64)
        pg.draw.rect(screen, (18, 39, 75), rect, border_radius=16)
        pg.draw.rect(screen, (70, 170, 255), rect, 2, border_radius=16)

        key_text = font.render(key, True, (120, 215, 255))
        screen.blit(key_text, (250, y + 16))
        screen.blit(font_small.render(name, True, (255, 255, 255)), (330, y + 10))
        screen.blit(font_small.render(description, True, (170, 195, 220)), (332, y + 34))


def write_text(text, position, color=(255, 255, 255), size=30):
    rendered_font = font if size == 30 else font_small
    text_surface = rendered_font.render(text, True, color)
    screen.blit(text_surface, position)


def reset_game():
    global position, velocity, angle, move_speed, move_acceleration
    global bullets, shooting_cooldown, shot_interval, bullet_speed, bullet_damage
    global asteroids, enemy_ships, enemy_spawn_timer, spawn_timer, boss, boss_bullets, next_boss_score
    global ship_health, score, palivo, fuel_level, fuel_requirement, upgrade_menu, upgrade_level, game_over
    global max_ship_health, particles, trail, paused, start_screen, damage_cooldown

    position = pg.Vector2(screen_width / 2, screen_height / 2)
    velocity = pg.Vector2()
    angle = 0
    move_speed = 500
    move_acceleration = 1200
    bullets = []
    shooting_cooldown = 0.0
    shot_interval = 0.5
    bullet_speed = 750
    bullet_damage = 1
    asteroids = []
    enemy_ships = []
    enemy_spawn_timer = 0.0
    spawn_timer = 0.0
    boss = None
    boss_bullets = []
    next_boss_score = 30
    ship_health = 5
    max_ship_health = 5
    score = 0
    palivo = 0
    fuel_level = 0
    fuel_requirement = 100
    upgrade_menu = False
    upgrade_level = 1
    particles = []
    trail = []
    game_over = False
    paused = False
    start_screen = False
    damage_cooldown = 0.0


def save_high_score():
    global high_score
    if score > high_score:
        high_score = score
        try:
            with open(high_score_file, "w", encoding="utf-8") as score_file:
                score_file.write(str(high_score))
        except OSError:
            pass


def draw_game_over():
    overlay = pg.Surface((screen_width, screen_height), pg.SRCALPHA)
    overlay.fill((3, 6, 20, 215))
    screen.blit(overlay, (0, 0))

    title = font_big.render("GAME OVER", True, (255, 130, 130))
    screen.blit(title, title.get_rect(center=(screen_width // 2, 290)))
    screen.blit(font.render(f"Score: {score}", True, (255, 255, 255)),
                font.render(f"Score: {score}", True, (255, 255, 255)).get_rect(
                    center=(screen_width // 2, 370)))
    screen.blit(font.render(f"Hi-Score: {high_score}", True, (110, 210, 255)),
                font.render(f"Hi-Score: {high_score}", True, (110, 210, 255)).get_rect(
                    center=(screen_width // 2, 420)))
    screen.blit(font.render("Press R to restart", True, (220, 235, 255)),
                font.render("Press R to restart", True, (220, 235, 255)).get_rect(
                    center=(screen_width // 2, 500)))


def draw_start_screen():
    draw_background(pg.time.get_ticks() / 1000.0)
    title = font_big.render("ASTEROIDS", True, (220, 245, 255))
    screen.blit(title, title.get_rect(center=(screen_width // 2, 280)))
    screen.blit(font.render("Space: Shoot", True, (255, 255, 255)),
                font.render("Space: Shoot", True, (255, 255, 255)).get_rect(
                    center=(screen_width // 2, 370)))
    screen.blit(font.render("WASD: Move", True, (255, 255, 255)),
                font.render("WASD: Move", True, (255, 255, 255)).get_rect(
                    center=(screen_width // 2, 410)))
    screen.blit(font.render("Mouse: Aim", True, (255, 255, 255)),
                font.render("Mouse: Aim", True, (255, 255, 255)).get_rect(
                    center=(screen_width // 2, 450)))
    prompt = font.render("Press ENTER to start", True, (110, 210, 255))
    screen.blit(prompt, prompt.get_rect(center=(screen_width // 2, 530)))


def draw_pause_screen():
    overlay = pg.Surface((screen_width, screen_height), pg.SRCALPHA)
    overlay.fill((3, 6, 20, 190))
    screen.blit(overlay, (0, 0))
    title = font_big.render("PAUSED", True, (235, 245, 255))
    screen.blit(title, title.get_rect(center=(screen_width // 2, 340)))
    prompt = font.render("Press P or ESC to continue", True, (110, 210, 255))
    screen.blit(prompt, prompt.get_rect(center=(screen_width // 2, 420)))


running = True

while running:
    dt = min(clock.tick(fps) / 1000.0, 0.05)
    time_value = pg.time.get_ticks() / 1000.0

    for event in pg.event.get():
        if event.type == pg.QUIT:
            running = False
        elif event.type == pg.KEYDOWN:
            if start_screen:
                if event.key == pg.K_RETURN:
                    reset_game()
                continue
            if event.key == pg.K_ESCAPE or event.key == pg.K_p:
                if not game_over and not upgrade_menu:
                    paused = not paused
            elif game_over:
                if event.key == pg.K_r:
                    reset_game()
            elif upgrade_menu:
                if event.key == pg.K_1:
                    shot_interval = max(0.12, shot_interval * 0.82)
                    upgrade_level += 1
                    upgrade_menu = False
                elif event.key == pg.K_2:
                    move_speed = min(760, move_speed + 60)
                    move_acceleration = min(1700, move_acceleration + 120)
                    upgrade_level += 1
                    upgrade_menu = False
                elif event.key == pg.K_3:
                    max_ship_health += 2
                    ship_health = min(max_ship_health, ship_health + 2)
                    upgrade_level += 1
                    upgrade_menu = False
                elif event.key == pg.K_4:
                    bullet_damage = min(5, bullet_damage + 1)
                    upgrade_level += 1
                    upgrade_menu = False
                elif event.key == pg.K_5:
                    max_ship_health += 3
                    ship_health = min(max_ship_health, ship_health + 3)
                    upgrade_level += 1
                    upgrade_menu = False
                elif event.key == pg.K_6:
                    bullet_speed = min(1200, bullet_speed + 150)
                    upgrade_level += 1
                    upgrade_menu = False

    if not running:
        break

    keys = pg.key.get_pressed()

    if start_screen:
        draw_start_screen()
        pg.display.flip()
        continue

    if game_over:
        draw_background(time_value)
        draw_game_over()
        pg.display.flip()
        continue

    if paused:
        draw_background(time_value)
        draw_pause_screen()
        pg.display.flip()
        continue

    if upgrade_menu:
        draw_background(time_value)
        draw_upgrade_menu()
        pg.display.flip()
        continue

    mouse_position = pg.Vector2(pg.mouse.get_pos())
    to_mouse = mouse_position - position
    if to_mouse.length_squared() > 0:
        angle = -pg.Vector2(0, -1).angle_to(to_mouse)
    direction = pg.Vector2(0, -1).rotate(-angle)

    movement = pg.Vector2(
        int(keys[pg.K_d]) - int(keys[pg.K_a]),
        int(keys[pg.K_s]) - int(keys[pg.K_w])
    )
    if movement.length_squared() > 0:
        movement = movement.normalize()
        velocity += movement * move_acceleration * dt

    velocity *= 0.96 ** (dt * fps)
    if velocity.length_squared() > move_speed ** 2:
        velocity.scale_to_length(move_speed)
    position += velocity * dt

    player_image = rotate_cached(player_original, player_rotation_cache, angle)
    half_width = player_image.get_width() / 2
    half_height = player_image.get_height() / 2
    position.x = max(half_width, min(screen_width - half_width, position.x))
    position.y = max(half_height, min(screen_height - half_height, position.y))
    if position.x in (half_width, screen_width - half_width):
        velocity.x = 0
    if position.y in (half_height, screen_height - half_height):
        velocity.y = 0

    player_rect = player_image.get_rect(center=(round(position.x), round(position.y)))

    shooting_cooldown = max(0.0, shooting_cooldown - dt)
    if keys[pg.K_SPACE] and shooting_cooldown <= 0:
        bullets.append(Bullet(position + direction * 38, direction))
        shooting_cooldown = shot_interval

    if boss is None and score >= next_boss_score:
        boss = spawn_boss()
        boss_bullets = []
        next_boss_score += 30

    if boss is None and len(asteroids) < max_asteroids + min(fuel_level, 8):
        spawn_timer += dt
        current_spawn_interval = max(0.22, spawn_interval - score * 0.012 - fuel_level * 0.035)
        if spawn_timer >= current_spawn_interval:
            spawn_timer -= current_spawn_interval
            asteroids.append(create_asteroid())
    elif boss is not None:
        asteroids = []
        target = position - boss["position"]
        if target.length_squared() > 0:
            target.normalize_ip()
        boss["position"].y += math.sin(time_value * 2.1 + boss["phase"]) * 80 * dt
        phase_two = boss["health"] <= boss["max_health"] * 0.5
        movement_speed = 55 if phase_two else 35
        boss["position"].x += target.x * movement_speed * dt
        boss["position"].x = max(100, min(screen_width - 100, boss["position"].x))
        boss["position"].y = max(130, min(screen_height - 170, boss["position"].y))

        boss["hit_flash"] = max(0.0, boss["hit_flash"] - dt)
        boss["shot_timer"] -= dt
        if boss["shot_timer"] <= 0:
            direction_to_player = position - boss["position"]
            if direction_to_player.length_squared() > 0:
                direction_to_player = direction_to_player.normalize()
                boss_bullets.append({
                    "position": boss["position"].copy(),
                    "velocity": direction_to_player * (360 if phase_two else 320),
                    "radius": 8
                })
                spreads = (-0.25, -0.12, 0.12, 0.25) if phase_two else (-0.18, 0.18)
                for spread in spreads:
                    boss_bullets.append({
                        "position": boss["position"].copy(),
                        "velocity": direction_to_player.rotate(spread) * (310 if phase_two else 290),
                        "radius": 7
                    })
            boss["shot_timer"] = max(0.38, boss_shot_interval - upgrade_level * 0.035)

        boss["burst_timer"] -= dt
        if boss["burst_timer"] <= 0:
            for spread in range(12):
                angle = math.tau * spread / 12 + time_value * 0.8
                boss_bullets.append({
                    "position": boss["position"].copy(),
                    "velocity": pg.Vector2(math.cos(angle), math.sin(angle)) * (220 if phase_two else 190),
                    "radius": 6
                })
            boss["burst_timer"] = 2.8 if phase_two else 4.2

    enemy_spawn_timer += dt
    current_enemy_spawn_interval = max(5.0, enemy_spawn_interval - fuel_level * 0.6)
    if enemy_spawn_timer >= current_enemy_spawn_interval and len(enemy_ships) < 4:
        enemy_spawn_timer = 0.0
        enemy_ships.append(create_enemy_ship())

    for enemy in enemy_ships:
        enemy["position"] += enemy["velocity"] * dt

    for index, asteroid in enumerate(asteroids):
        asteroid["position"] += asteroid["velocity"] * dt
        if asteroid_outside_screen(asteroid):
            asteroids[index] = create_asteroid()

    surviving_bullets = []
    hit_asteroids = set()

    for bullet in bullets:
        bullet.update(dt)
        if bullet.outside_screen():
            continue

        hit = False
        if boss is not None:
            collision_radius = bullet.radius + boss["radius"]
            if bullet.position.distance_squared_to(boss["position"]) <= collision_radius ** 2:
                boss["health"] -= bullet_damage
                boss["hit_flash"] = 0.10
                hit = True
                create_explosion(bullet.position, False)
                if boss["health"] <= 0:
                    create_explosion(boss["position"], True)
                    score += 10
                    palivo = min(100, palivo + 50)
                    boss = None
                    boss_bullets = []

        if hit:
            continue

        for enemy in enemy_ships:
            collision_radius = bullet.radius + enemy["radius"]
            if bullet.position.distance_squared_to(enemy["position"]) <= collision_radius ** 2:
                enemy["health"] -= bullet_damage
                hit = True
                if enemy["health"] <= 0:
                    enemy_ships.remove(enemy)
                    score += 2
                    create_explosion(enemy["position"], True)
                break

        if hit:
            continue

        for index, asteroid in enumerate(asteroids):
            if index in hit_asteroids:
                continue
            collision_radius = bullet.radius + asteroid["radius"]
            if bullet.position.distance_squared_to(asteroid["position"]) <= collision_radius ** 2:
                hit_asteroids.add(index)
                hit = True
                score += 1
                if asteroid["blue_smoke"]:
                    palivo += 20
                create_explosion(asteroid["position"], asteroid["blue_smoke"])
                break

        if not hit:
            surviving_bullets.append(bullet)

    bullets = surviving_bullets

    damage_cooldown = max(0.0, damage_cooldown - dt)
    player_hit_asteroids = set()
    if damage_cooldown <= 0:
        for index, asteroid in enumerate(asteroids):
            collision_radius = player_radius + asteroid["radius"]
            if position.distance_squared_to(asteroid["position"]) <= collision_radius ** 2:
                player_hit_asteroids.add(index)

    for index in player_hit_asteroids:
        create_explosion(asteroids[index]["position"], asteroids[index]["blue_smoke"])
        asteroids[index] = create_asteroid()
        ship_health -= 1
        damage_cooldown = 1.0

    if damage_cooldown <= 0:
        for enemy in enemy_ships[:]:
            if position.distance_squared_to(enemy["position"]) <= (player_radius + enemy["radius"]) ** 2:
                enemy_ships.remove(enemy)
                create_explosion(enemy["position"], True)
                ship_health -= 1
                damage_cooldown = 1.0
                break
        if boss is not None and damage_cooldown <= 0:
            if position.distance_squared_to(boss["position"]) <= (player_radius + boss["radius"]) ** 2:
                create_explosion(position, True)
                ship_health -= 2
                damage_cooldown = 1.0

    for index in hit_asteroids:
        asteroids[index] = create_asteroid()

    surviving_boss_bullets = []
    damage_cooldown = max(0.0, damage_cooldown - dt)
    for boss_bullet in boss_bullets:
        boss_bullet["position"] += boss_bullet["velocity"] * dt
        if (boss_bullet["position"].x < -30 or boss_bullet["position"].x > screen_width + 30
                or boss_bullet["position"].y < -30 or boss_bullet["position"].y > screen_height + 30):
            continue
        if (damage_cooldown <= 0
                and boss_bullet["position"].distance_squared_to(position)
                <= (boss_bullet["radius"] + player_radius) ** 2):
            create_explosion(boss_bullet["position"], True)
            ship_health -= 2
            damage_cooldown = 1.0
            continue
        surviving_boss_bullets.append(boss_bullet)
    boss_bullets = surviving_boss_bullets

    while palivo >= fuel_requirement:
        palivo -= fuel_requirement
        fuel_level += 1
        fuel_requirement = max(fuel_requirement + 25, round(fuel_requirement * 1.2))
        upgrade_menu = True

    if ship_health <= 0:
        save_high_score()
        game_over = True

    surviving_particles = []
    for particle in particles:
        particle["position"] += particle["velocity"] * dt
        particle["velocity"] *= 0.97 ** (dt * fps)
        particle["life"] -= dt
        if particle["life"] > 0:
            surviving_particles.append(particle)
    particles = surviving_particles

    draw_background(time_value)

    for asteroid in asteroids:
        draw_asteroid(asteroid, time_value)

    for enemy in enemy_ships:
        draw_enemy_ship(enemy)

    if boss is not None:
        draw_boss(boss, time_value)
        for boss_bullet in boss_bullets:
            pg.draw.circle(screen, (255, 180, 80),
                           (round(boss_bullet["position"].x), round(boss_bullet["position"].y)),
                           boss_bullet["radius"])
            pg.draw.circle(screen, (255, 70, 90),
                           (round(boss_bullet["position"].x), round(boss_bullet["position"].y)),
                           boss_bullet["radius"] + 4, 2)

    for particle in particles:
        life_ratio = max(0.0, particle["life"] / particle["max_life"])
        radius = max(1, round(5 * life_ratio))
        color = (80, 190, 255) if particle["blue"] else (255, 170, 90)
        pg.draw.circle(screen, color,
                       (round(particle["position"].x), round(particle["position"].y)), radius)

    for bullet in bullets:
        bullet.draw(screen)

    # Jemná svetelná stopa pod lodou
    pg.draw.circle(screen, (40, 115, 210),
                   (round(position.x), round(position.y)), 34, 2)
    screen.blit(player_image, player_rect)

    # HUD
    pg.draw.rect(screen, (10, 20, 45), pg.Rect(8, 8, 230, 96), border_radius=12)
    pg.draw.rect(screen, (55, 125, 210), pg.Rect(8, 8, 230, 96), 2, border_radius=12)
    write_text(f"Health: {ship_health} / {max_ship_health}", (24, 20), (255, 150, 150), 30)
    write_text(f"Score: {score}", (24, 50), (255, 255, 255), 30)
    write_text(f"Fuel: {min(palivo, fuel_requirement)} / {fuel_requirement}",
               (24, 80), (110, 210, 255), 30)

    pg.draw.rect(screen, (20, 45, 80), pg.Rect(24, 108, 180, 12), border_radius=6)
    pg.draw.rect(screen, (70, 190, 255),
                 pg.Rect(24, 108, 180 * min(palivo, fuel_requirement) // fuel_requirement, 12),
                 border_radius=6)

    pg.display.flip()

pg.quit()
