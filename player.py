import pygame
import os
import yaml
import json
from config import WIDTH, HEIGHT
from math import ceil


def load_character_sprites(name: str, scale: int) -> (dict[str, list[pygame.surface.Surface]], dict[str, int]):
    path = os.path.join("data", "PlayerSprites", name)
    ch_data = {}
    with open(os.path.join(path, '_config.yaml'), "r") as stream:
        try:
            data = yaml.safe_load(stream)
            ch_data['RECT_WIDTH'] = data['RECT_WIDTH']
            ch_data['RECT_HEIGHT'] = data['RECT_HEIGHT']
            ch_data['CHARACTER_WIDTH'] = data['CHARACTER_WIDTH']
            ch_data['CHARACTER_HEIGHT'] = data['CHARACTER_HEIGHT']
            ch_data['SPRITES_CHANGE_RATE'] = data['SPRITES_CHANGE_RATE']
        except yaml.YAMLError as exc:
            print(exc)

    sprites_dict: dict[str, list[pygame.surface.Surface]] = dict()
    for filename in os.listdir(path):
        if '.png' not in filename:
            continue
        state = filename.replace('.png', '')
        sprites_dict[state + "_right"] = []
        sprites_dict[state + "_left"] = []
        sprite_sheet = pygame.image.load(os.path.join(path, filename))
        sprites_count = sprite_sheet.get_width() // ch_data['RECT_WIDTH']
        for i in range(sprites_count):
            sprite = sprite_sheet.subsurface((ch_data['RECT_WIDTH'] * i, 0),
                                             (ch_data['RECT_WIDTH'], ch_data['RECT_HEIGHT']))
            sprite = pygame.transform.scale(sprite, (ch_data['RECT_WIDTH'] * scale, ch_data['RECT_HEIGHT'] * scale))
            sprites_dict[state + "_right"].append(sprite)
            sprites_dict[state + "_left"].append(pygame.transform.flip(sprite, True, False))


    return sprites_dict, ch_data


class Player(pygame.sprite.Sprite):
    def __init__(self, pos, scale, name):
        super().__init__()
        self.sprites, self.ch_data = load_character_sprites(name, scale)
        self.rect: pygame.Rect = pygame.rect.Rect(pos, (
            self.ch_data['RECT_WIDTH'] * scale, self.ch_data['RECT_HEIGHT'] * scale))

        temp = pygame.Surface((self.ch_data['RECT_WIDTH'] * scale, self.ch_data['RECT_HEIGHT'] * scale),
                              pygame.SRCALPHA, 32)
        self.sprite_offset_x = (self.ch_data['RECT_WIDTH'] - self.ch_data['CHARACTER_WIDTH']) // 2
        self.sprite_offset_y = self.ch_data['RECT_HEIGHT'] - self.ch_data['CHARACTER_HEIGHT']
        pygame.draw.rect(temp, (255, 255, 255), (
            self.sprite_offset_x, self.sprite_offset_y, self.ch_data['CHARACTER_WIDTH'],
            self.ch_data['CHARACTER_HEIGHT']))
        self.mask = pygame.mask.from_surface(temp)

        self.sprite: pygame.Surface = None

        self.v = 256  # В пикселях в секунду
        self.vx = 0
        self.vy = 0
        self.x, self.y = pos

        self.off_ground_counter = 0
        self.jump_counter = 0
        self.animations_counter = 0
        self.sprites_change_rate = self.ch_data['SPRITES_CHANGE_RATE']

        self.status = 'idle'
        self.direction = 'right'

        self.sprite_animation_counter = 0

        self.inventory = []
        self.current_weapons = []
        self.is_holding_weapon = False



    def draw_weapon_and_hands(self, screen, offset_x, offset_y):
        if self.is_holding_weapon:
            #Рисуем оружие в левой и правой руке
            pass
        else:
            #рисуем просто руки
            screen.blit(self.sprite, (self.rect.x + offset_x, self.rect.y + offset_y))

    def get_position(self):
        x = self.x + self.ch_data['RECT_WIDTH'] // 2
        y = self.y + self.ch_data['RECT_HEIGHT'] - self.ch_data['CHARACTER_HEIGHT']
        return x, y

    def update_sprite(self, time_delta):
        self.status = 'idle'

        if self.vy < 0:
            self.status = 'jump'
        elif self.vy * time_delta > 2:
            self.status = 'fall'
        elif self.vx != 0:
            self.status = 'run'


        sprite_name = self.status + '_' + self.direction
        sprite_index = (self.sprite_animation_counter // self.sprites_change_rate) % len(self.sprites[sprite_name])
        self.sprite = self.sprites[sprite_name][sprite_index]
        self.sprite_animation_counter += 1

    def move_left(self):
        self.direction = 'left'
        self.vx = -self.v

    def move_right(self):
        self.direction = 'right'
        self.vx = self.v

    def move(self, dx, dy):
        self.x += dx
        self.rect.x = self.x

        # Надо пофиксить
        self.y += dy
        self.rect.y = self.y

    def jump(self):
        if self.jump_counter == 0:
            self.off_ground_counter = 0
            self.vy = -600
            self.jump_counter += 1

    def touch_down(self):
        self.off_ground_counter = 0
        self.jump_counter = 0
        self.vy = 0

    def touch_ceil(self):
        self.vy *= -1

    def loop(self, time_delta):
        self.update_sprite(time_delta)
        self.vy += min(1, self.off_ground_counter) * time_delta * 2000
        self.off_ground_counter += 1
        self.move(self.vx * time_delta, self.vy * time_delta)

    def draw(self, screen, offset_x, offset_y):
        screen.blit(self.sprite, (self.rect.x + offset_x, self.rect.y + offset_y))
      #  self.draw_weapon_and_hands(self.sprite, (self.rect.x + offset_x, self.rect.y + offset_y))

    def encode(self):
        return json.dumps([self.rect.x, self.rect.y, self.status, self.direction, self.sprite_animation_counter])

    def apply(self, data):
        self.rect.x = data[0]
        self.rect.y = data[1]
        self.status = data[2]
        self.direction = data[3]
        self.sprite_animation_counter = data[4] - 1
        sprite_name = self.status + '_' + self.direction
        sprite_index = (self.sprite_animation_counter // self.sprites_change_rate) % len(self.sprites[sprite_name])
        self.sprite = self.sprites[sprite_name][sprite_index]

