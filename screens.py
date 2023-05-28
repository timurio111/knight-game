import os

import pygame.event

from config import WIDTH, HEIGHT
from event_codes import *
from gui_elements import Button, TextInput
from sound import SoundCore

def load_background(image_name: str) -> pygame.Surface:
    path = os.path.join("data", "Background", image_name)
    image = pygame.transform.scale(pygame.image.load(path), (WIDTH, HEIGHT))
    return image.convert()


class Menu:
    def __init__(self):
        self.visible = True
        self.background = load_background("gradient2.png")
        self.button_start_server = Button(size=(WIDTH // 2, HEIGHT // 12),
                                          pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2),
                                          event=pygame.event.Event(START_SERVER_MENU_EVENT),
                                          text="Start server",
                                          font='data/fonts/menu_font.ttf')
        self.button_connect = Button(size=(WIDTH // 2, HEIGHT // 12),
                                     pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2 + HEIGHT // 8),
                                     event=pygame.event.Event(OPEN_CONNECTION_MENU_EVENT),
                                     text="Connect to server",
                                     font='data/fonts/menu_font.ttf')
        self.button_exit = Button(size=(WIDTH // 4.2, HEIGHT // 12),
                                  pos=(3 * WIDTH // 4 - WIDTH // 4.2, HEIGHT // 2 + 2 * HEIGHT // 8),
                                  event=pygame.event.Event(EXIT_GAME_EVENT),
                                  text="Quit", font='data/fonts/menu_font.ttf')
        self.button_settings = Button(size=(WIDTH // 4.2, HEIGHT // 12),
                                      pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2 + 2 * HEIGHT // 8),
                                      event=pygame.event.Event(OPEN_SETTINGS_MENU_EVENT),
                                      text="Settings",
                                      font='data/fonts/menu_font.ttf')

    def draw(self, screen: pygame.Surface):
        screen.blit(self.background, (0, 0))
        self.button_connect.draw(screen, 1)
        self.button_start_server.draw(screen, 1)
        self.button_settings.draw(screen, 1)
        self.button_exit.draw(screen, 1)


class ConnectToServerMenu:
    def __init__(self):
        self.background = load_background('gradient1.png')
        self.button_back = Button(size=(WIDTH // 5, 40),
                                  pos=(10, 10),
                                  text="Back",
                                  event=pygame.event.Event(OPEN_MAIN_MENU_EVENT))
        self.text_input_address = TextInput(size=(WIDTH // 1.1, 25),
                                            pos=((WIDTH - WIDTH // 1.1) // 2, HEIGHT // 2),
                                            hint="server address",
                                            text="",
                                            font='data/fonts/menu_font.ttf')

        self.button_start_game = Button(size=(WIDTH // 5, 40),
                                        pos=(WIDTH - WIDTH // 5 - 10, HEIGHT - 40 - 10),
                                        text="Connect",
                                        event=pygame.event.Event(CONNECT_TO_SERVER_EVENT, ))

    def event_handle(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
            connect_event = pygame.event.Event(CONNECT_TO_SERVER_EVENT)
            connect_event.dict['input'] = self.text_input_address.text
            pygame.event.post(connect_event)

            return
        self.text_input_address.event_handle(event)
        self.button_start_game.event.dict['input'] = self.text_input_address.text

    def draw(self, screen: pygame.Surface):
        screen.blit(self.background, (0, 0))
        self.text_input_address.draw(screen, 1)
        self.button_back.draw(screen, 1)
        self.button_start_game.draw(screen, 1)


class StartServerMenu:
    def __init__(self):
        self.background = load_background('gradient1.png')
        self.button_back = Button(size=(WIDTH // 5, 40),
                                  pos=(10, 10),
                                  text="Back",
                                  event=pygame.event.Event(OPEN_MAIN_MENU_EVENT))
        self.text_input_address = TextInput(size=(WIDTH // 1.1, 25),
                                            pos=((WIDTH - WIDTH // 1.1) // 2, HEIGHT // 2),
                                            hint="server address",
                                            text="",
                                            font='data/fonts/menu_font.ttf')

        self.button_start_game = Button(size=(WIDTH // 5, 40),
                                        pos=(WIDTH - WIDTH // 5 - 10, HEIGHT - 40 - 10),
                                        text="Start server",
                                        event=pygame.event.Event(CONNECT_TO_SERVER_EVENT, ))

    def event_handle(self, event):
        self.text_input_address.event_handle(event)
        self.button_start_game.event.dict['input'] = self.text_input_address.text

    def draw(self, screen: pygame.Surface):
        screen.blit(self.background, (0, 0))
        self.text_input_address.draw(screen, 1)
        self.button_back.draw(screen, 1)
        self.button_start_game.draw(screen, 1)


class MessageScreen:
    def __init__(self, message, event):
        self.set_text(message)
        self.button_ok = Button(size=(WIDTH // 5, 40),
                                pos=(WIDTH - WIDTH // 5 - 10, HEIGHT - 40 - 10),
                                text="Ok",
                                event=event)

    def set_text(self, text):
        self.text = text
        font = pygame.font.Font(None, 100)
        self.image = pygame.Surface((WIDTH, HEIGHT))
        self.image.fill((0, 0, 0))
        text_image = font.render(self.text, True, (255, 255, 255))

        text_image = pygame.transform.scale_by(text_image, WIDTH / text_image.get_width())
        self.image.blit(text_image, (WIDTH // 2 - text_image.get_width() // 2,
                                     HEIGHT // 2 - text_image.get_height() // 2))

    def draw(self, screen):
        screen.blit(self.image, (0, 0))
        self.button_ok.draw(screen, 1)


class LoadingScreen:
    def __init__(self, text='Waiting...'):
        self.set_text(text)
        self.visible = False

    def set_text(self, text):
        self.text = text
        font = pygame.font.Font(None, 100)
        self.image = pygame.Surface((WIDTH, HEIGHT))
        self.image.fill((0, 0, 0))
        text_image = font.render(self.text, True, (255, 255, 255))
        self.image.blit(text_image, (WIDTH // 2 - text_image.get_width() // 2,
                                     HEIGHT // 2 - text_image.get_height() // 2))

    def draw(self, screen):
        screen.blit(self.image, (0, 0))


class SettingsMenu:
    def __init__(self):
        self.visible = True
        self.background = load_background("gradient2.png")
        self.change_window_mode = Button(size=(WIDTH // 4.2, HEIGHT // 12),
                                         pos=(3 * WIDTH // 4 - WIDTH // 4.2, HEIGHT // 2 + 2 * HEIGHT // 8),
                                         event=pygame.event.Event(START_SERVER_MENU_EVENT),
                                         text="Change Window Mode",
                                         font='data/fonts/menu_font.ttf')
        self.music_off = Button(size=(WIDTH // 2, HEIGHT // 12),
                                pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2 + HEIGHT // 8),
                                event=pygame.event.Event(CHANGE_MUSIC_MODE),
                                text='Music off' if SoundCore.is_music_on else 'Music on',
                                font='data/fonts/menu_font.ttf')
        self.sounds_off = Button(size=(WIDTH // 2, HEIGHT // 12),
                                 pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2),

                                 event=pygame.event.Event(CHANGE_SOUND_MODE),
                                 text='Sound off' if SoundCore.is_sound_on else 'Sound on', font='data/fonts/menu_font.ttf')
        self.return_back = Button(size=(WIDTH // 4.2, HEIGHT // 12),
                                  pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2 + 2 * HEIGHT // 8),
                                  event=pygame.event.Event(OPEN_MAIN_MENU_EVENT),
                                  text="To Menu",
                                  font='data/fonts/menu_font.ttf')

    def buttons_update(self):
        self.sounds_off = Button(size=(WIDTH // 2, HEIGHT // 12),
                                 pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2),
                                 event=pygame.event.Event(CHANGE_SOUND_MODE),
                                 text='Sound off' if SoundCore.is_sound_on else 'Sound on', font='data/fonts/menu_font.ttf')
        self.music_off = Button(size=(WIDTH // 2, HEIGHT // 12),
                                pos=(WIDTH // 2 - WIDTH // 4, HEIGHT // 2 + HEIGHT // 8),
                                event=pygame.event.Event(CHANGE_MUSIC_MODE),
                                text='Music off' if SoundCore.is_music_on else 'Music on',
                                font='data/fonts/menu_font.ttf')
    def draw(self, screen: pygame.Surface):
        screen.blit(self.background, (0, 0))
        self.change_window_mode.draw(screen, 1)
        self.music_off.draw(screen, 1)
        self.sounds_off.draw(screen, 1)
        self.return_back.draw(screen, 1)

