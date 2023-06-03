from __future__ import annotations

import asyncio
import time

import pygame

from colors import color_generator
from level import Level, GameObjectPoint
from network import DataPacket
from weapon import Weapon

DEBUG = True
TICK_RATE = 240
POSITIONS_SEND_RATE = 120

server = "127.0.0.1"
tcp_port = 5555
udp_port = 5556

current_id = 0
id_to_stream: dict[int, tuple[asyncio.StreamReader, asyncio.StreamWriter]] = {}
id_to_udp_address: dict[int, tuple[str, int]] = {}
client_socket_to_id: dict[tuple[asyncio.StreamReader, asyncio.StreamWriter], int] = {}
id_to_last_udp_packet_time: dict[int, float] = {}

start_time = int(time.time())


class GameStatistics:
    def __init__(self):
        self.players_data = {}

    def new_player(self, player_id: int):
        self.players_data[player_id] = {'kill': 0, 'death': 0, 'win': 0, 'damage': 0}

    def sort_by_rating(self):
        rating = list(self.players_data.keys())
        rating.sort(key=lambda player: (self[player]['win'], self[player]['kill'], -self[player]['death']), reverse=True)
        return rating

    def __getitem__(self, item):
        return self.players_data[item]

    def __setitem__(self, key, value):
        self.players_data[key] = value


game_statistics = GameStatistics()


class ServerPlayer:
    def __init__(self, player_id: int, x: int, y: int, status: str, direction: str, sprite_animation_counter: int,
                 hp: int, ch_data: dict, color: list):
        self.id: int = player_id
        self.x = x
        self.y = y
        self.status = status
        self.direction: str = direction
        self.sprite_animation_counter = sprite_animation_counter
        self.hp = hp
        self.ch_data = ch_data
        self.vx = 0
        self.vy = 0
        self.off_ground_counter = 0
        self.sprite_offset_x: int = (self.ch_data['RECT_WIDTH'] - self.ch_data['CHARACTER_WIDTH']) // 2
        self.sprite_offset_y: int = self.ch_data['RECT_HEIGHT'] - self.ch_data['CHARACTER_HEIGHT']
        self.sprite_rect = pygame.Rect((self.x + self.sprite_offset_x, self.y + self.sprite_offset_y),
                                       (ch_data['CHARACTER_WIDTH'], ch_data['CHARACTER_HEIGHT']))
        self.weapon_id = -1
        self.color = color
        self.flags: set[int] = set()

    @staticmethod
    def from_player_data(player_id, data) -> ServerPlayer:
        return ServerPlayer(player_id, *data)

    def apply(self, data) -> None:
        self.x, self.y, self.status, self.direction, self.sprite_animation_counter, self.hp, \
            self.vx, self.vy, self.off_ground_counter = data
        self.sprite_rect.x = self.x + self.sprite_offset_x
        self.sprite_rect.y = self.y + self.sprite_offset_y

    def get_center(self) -> tuple[int, int]:
        return self.sprite_rect.x + self.ch_data['CHARACTER_WIDTH'] // 2, self.sprite_rect.bottom

    def encode(self) -> list:
        return [self.x, self.y, self.status, self.direction, self.sprite_animation_counter, self.hp,
                self.vx, self.vy, self.off_ground_counter, self.color]

    def take_damage(self, bullet: ServerBullet):
        self.hp -= bullet.damage
        game_statistics[bullet.owner]['damage'] += min(bullet.damage, self.hp)
        if self.hp <= 0:
            self.death()
            game_statistics[bullet.owner]['kill'] += 1

    def death(self):
        self.hp = 0
        game_statistics[self.id]['death'] += 1
        game_state.players_alive.remove(self.id)

    def __repr__(self):
        return str((self.x, self.y, self.hp))


class ServerBullet:
    bullet_id = 0

    def __init__(self, owner: int, pos: tuple[int, int], v: tuple[int, int], damage: int, ay: int):
        self.owner = owner
        self.ay = ay
        self.x, self.y = pos
        self.vx, self.vy = v
        self.damage = damage
        self.current_lifetime_seconds = 0
        self.max_lifetime_seconds = 1

    @staticmethod
    def from_data(owner: int, data: list):
        return ServerBullet(owner, *data)

    def update(self, timedelta: int) -> None:
        self.vy += self.ay
        self.current_lifetime_seconds += timedelta
        self.x += self.vx * timedelta
        self.y += self.vy * timedelta

    def get_position(self) -> tuple[int, int]:
        return self.x, self.y


class ServerWeapon:
    weapon_id = 0

    def __init__(self, name, x, y):
        self.owner = None
        self.name = name
        self.vy = 0

        self.ammo = Weapon.all_weapons_info[self.name]['PATRONS']

        weapon_rect_height = Weapon.all_weapons_info[name]['WEAPON_RECT_HEIGHT']
        weapon_rect_width = Weapon.all_weapons_info[name]['WEAPON_RECT_WIDTH']
        image_offset_x = Weapon.all_weapons_info[name]['IMAGE_OFFSET_X']
        image_offset_y = Weapon.all_weapons_info[name]['IMAGE_OFFSET_Y']
        image_width = Weapon.all_weapons_info[name]['IMAGE_WIDTH']
        image_height = Weapon.all_weapons_info[name]['IMAGE_HEIGHT']

        self.center_offset_x = image_offset_x + image_width // 2
        self.center_offset_y = image_offset_x + image_height // 2
        self.bottom_offset_y = image_offset_y + image_height
        self.rect = pygame.Rect(x - self.center_offset_x, y - self.bottom_offset_y,
                                weapon_rect_width, weapon_rect_height)
        self.direction = 'right'

    def update(self, time_delta, level):
        time_delta = min(1 / 20, time_delta)
        if self.owner not in game_state.players_alive:
            self.owner = None
        if self.owner:
            owner = game_state.players[self.owner]
            self.direction = owner.direction
            self.rect.x = owner.x + Weapon.all_weapons_info[self.name][f'OFFSET_X_{self.direction.upper()}']
            self.rect.y = owner.y + Weapon.all_weapons_info[self.name]['OFFSET_Y']
        else:
            dvy = 128
            dy = int(time_delta * self.vy)
            self.rect.y += dy
            if level.collide_point(*self.get_center()):
                self.rect.y -= dy
                self.vy = 0
            else:
                self.vy += dvy
                self.vy = min(self.vy, 512)

    def get_center(self) -> tuple[int, int]:
        if self.direction == 'right':
            return self.rect.x + self.center_offset_x, self.rect.y + self.bottom_offset_y
        elif self.direction == 'left':
            return self.rect.right - self.center_offset_x, self.rect.y + self.bottom_offset_y

    def pick_up(self, player_id):
        self.owner = player_id
        game_state.players[player_id].weapon_id = self.weapon_id

    def encode(self):
        return [self.name, self.rect.x, self.rect.y, self.ammo]


class GameState:
    STATUS_WAIT = 1
    STATUS_CONNECTED = 2
    STATUS_PLAYING = 3
    MAX_LEVELS = 10

    def __init__(self):
        self.level_id = 0

        self.players: dict[int, ServerPlayer] = dict()
        self.players_alive: set[int] = set()
        self.bullets: dict[int, ServerBullet] = dict()
        self.weapons: dict[int, ServerWeapon] = dict()

        self.level_name: str = 'lobby'
        self.lastlevel: bool = False
        self.level: Level = Level(self.level_name)
        self.spawn_points: list[GameObjectPoint] = []
        self.current_spawn_point: int = 0
        self.change_level(self.level_name)

        self.game_ended = False
        self.game_started = False

    def change_level(self, level_name) -> None:
        self.level_id += 1
        self.players_alive = set(self.players.keys())
        self.level_name = level_name
        for player_id, player in self.players.items():
            if DataPacket.FLAG_READY in player.flags:
                player.flags.remove(DataPacket.FLAG_READY)
        self.current_spawn_point = 0
        self.spawn_points.clear()

        self.bullets.clear()
        self.weapons.clear()
        ServerBullet.bullet_id = 0
        ServerWeapon.weapon_id = 0

        self.level = Level(level_name)
        for point in self.level.objects['points']:
            if point.name == 'spawnpoint':
                self.spawn_points.append(point)
            if 'Weapon' in point.name:
                self.weapons[ServerWeapon.weapon_id] = ServerWeapon(point.name, point.x, point.y)
                ServerWeapon.weapon_id += 1

    def get_spawn_point(self) -> tuple[int, int]:
        spawn_point = self.spawn_points[self.current_spawn_point]
        self.current_spawn_point = (self.current_spawn_point + 1) % len(self.spawn_points)
        return spawn_point.x, spawn_point.y


game_state = GameState()


async def accept_connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    global current_id, client_socket_to_id, id_to_stream

    client_id = current_id

    id_to_stream[client_id] = (reader, writer)
    client_socket_to_id[(reader, writer)] = current_id
    id_to_last_udp_packet_time[client_id] = 0
    current_id += 1

    if game_state.game_started:
        response = DataPacket(DataPacket.GAME_ALREADY_STARTED)
        await send(client_id, response)
        await disconnect(client_id)
        return

    game_statistics.new_player(client_id)
    auth_data = {'id': client_id}
    response = DataPacket(DataPacket.AUTH, auth_data)
    await send(client_id, response)

    print(f"New connection. Id={client_id}")

    game_data = {'level_name': 'lobby', 'position': game_state.get_spawn_point(), 'color': color_generator.__next__()}
    response = DataPacket(DataPacket.GAME_INFO, game_data)
    await send(client_id, response)

    while True:
        try:
            data = await read(reader)
        except Exception as e:
            print(type(e))
            break
        if data == b'':
            break
        data_packet = DataPacket.from_bytes(data)
        await handle_packet(data_packet)

    await disconnect(client_id)


async def disconnect(client_id: int):
    reader, writer = id_to_stream[client_id]
    client_id = client_socket_to_id[(reader, writer)]

    if client_id in game_state.players_alive:
        game_state.players[client_id].death()
    if client_id in game_state.players.keys():
        game_state.players.pop(client_id)
        id_to_stream.pop(client_id)
        id_to_udp_address.pop(client_id)
        id_to_last_udp_packet_time.pop(client_id)
        client_socket_to_id.pop((reader, writer))
    writer.close()
    await writer.wait_closed()
    print(f'client with id {client_id} disconnected')


async def read(reader: asyncio.StreamReader) -> bytes:
    return await reader.readline()


async def send_players_data(client_id: int, protocol):
    players_data = dict()
    for player_id in game_state.players.keys():
        if GameState.STATUS_PLAYING not in game_state.players[player_id].flags:
            continue
        players_data[player_id] = game_state.players[player_id].encode()
    response = DataPacket(DataPacket.PLAYERS_INFO, players_data)

    protocol.send(client_id, response)


async def send(client_id: int, data_packet: DataPacket):
    _, writer = id_to_stream[client_id]
    data_packet.headers['game_id'] = game_state.level_id
    writer.write(data_packet.encode())
    await writer.drain()


def spawn_players():
    if game_state.lastlevel:
        for player_id in game_statistics.sort_by_rating():
            if player_id not in game_state.players.keys():
                continue
            game_state.players[player_id].hp = 100
            spawn_pos = game_state.get_spawn_point()
            yield player_id, spawn_pos
    else:
        for player_id in game_state.players.keys():
            game_state.players[player_id].hp = 100
            spawn_pos = game_state.get_spawn_point()
            yield player_id, spawn_pos


async def end_game(n_players):
    game_state.lastlevel = True
    await change_level('lastmap' + str(n_players))


async def change_level(level_name):
    game_state.game_ended = False
    game_state.change_level(level_name)
    gen_spawn = spawn_players()
    for player_id, spawn_pos in gen_spawn:
        player_color = game_state.players[player_id].color
        game_data = {'level_name': game_state.level_name, 'position': spawn_pos, 'color': player_color}
        game_state.players[player_id].x, game_state.players[player_id].y = spawn_pos

        response = DataPacket(DataPacket.GAME_INFO, game_data)
        if GameState.STATUS_PLAYING in game_state.players[player_id].flags:
            game_state.players[player_id].flags.remove(GameState.STATUS_PLAYING)
        await send(player_id, response)

        for weapon_id, weapon in game_state.weapons.items():
            weapon_data = {'weapon_id': weapon_id, 'weapon_data': weapon.encode()}
            response = DataPacket(DataPacket.NEW_WEAPON_FROM_SERVER, weapon_data)
            await send(player_id, response)

    if game_state.lastlevel:
        await asyncio.sleep(5)
        for player_id in game_state.players.keys():
            response = DataPacket(DataPacket.DISCONNECT, {'statistics': game_statistics.players_data})
            await send(player_id, response)
        await asyncio.sleep(5)  # хз, вроде, стало стабильнее
        quit(0)


async def handle_packet(data_packet: DataPacket):
    client_id: int = data_packet.headers['id']

    if client_id == -1:
        return

    if data_packet.headers['game_id'] != game_state.level_id:
        return

    if data_packet.data_type == DataPacket.INITIAL_INFO:
        data = data_packet['data']
        game_state.players[client_id] = ServerPlayer.from_player_data(client_id, data)
        game_state.players[client_id].flags.add(GameState.STATUS_PLAYING)

    if data_packet.data_type == DataPacket.CLIENT_PLAYER_INFO:
        if GameState.STATUS_PLAYING in game_state.players[client_id].flags:
            data = data_packet['data']
            game_state.players[client_id].apply(data)

    if data_packet.data_type == DataPacket.ADD_PLAYER_FLAG:
        game_state.players[client_id].flags.add(data_packet['data'])

    if data_packet.data_type == DataPacket.REMOVE_PLAYER_FLAG:
        flag = data_packet['data']
        if flag in game_state.players[client_id].flags:
            game_state.players[client_id].flags.remove(flag)

    if data_packet.data_type == DataPacket.NEW_SHOT_FROM_CLIENT:
        bullet_data = data_packet['data']
        bullet = ServerBullet.from_data(client_id, bullet_data)
        bullet_id = ServerBullet.bullet_id
        ServerBullet.bullet_id += 1

        game_state.bullets[bullet_id] = bullet

        response = DataPacket(DataPacket.NEW_SHOT_FROM_SERVER, [client_id, bullet_id, bullet_data])
        for client_id in id_to_stream.keys():
            await send(client_id, response)

    if data_packet.data_type == DataPacket.CLIENT_PICK_WEAPON_REQUEST:
        closest_weapon_id = None
        min_dist = 1e9
        for weapon_id, weapon in game_state.weapons.items():

            if weapon.owner is not None:
                continue
            distance = pygame.math.Vector2(weapon.get_center()).distance_to(game_state.players[client_id].get_center())
            if distance > 32:
                continue
            if distance < min_dist:
                min_dist = distance
                closest_weapon_id = weapon_id

        if closest_weapon_id is not None:
            game_state.weapons[closest_weapon_id].owner = client_id
            response = DataPacket(DataPacket.CLIENT_PICKED_WEAPON,
                                  {'owner_id': client_id, 'weapon_id': closest_weapon_id})
            for client_id in id_to_stream.keys():
                await send(client_id, response)

    if data_packet.data_type == DataPacket.CLIENT_DROPPED_WEAPON:
        weapon_id = data_packet['weapon_id']
        weapon_direction = data_packet['weapon_direction']
        weapon_position = data_packet['weapon_position']
        weapon_ammo = data_packet['weapon_ammo']
        game_state.weapons[weapon_id].owner = None
        game_state.weapons[weapon_id].rect.x, game_state.weapons[weapon_id].rect.y = weapon_position
        game_state.weapons[weapon_id].direction = weapon_direction
        response = DataPacket(DataPacket.CLIENT_DROPPED_WEAPON,
                              {'owner_id': client_id,
                               'weapon_id': weapon_id,
                               'weapon_position': weapon_position,
                               'weapon_direction': weapon_direction,
                               'weapon_ammo': weapon_ammo})
        for client_id in id_to_stream.keys():
            await send(client_id, response)


async def update(time_delta):
    # Игроков не осталось
    if not game_state.players:
        if game_state.level_name != 'lobby':
            await change_level('lobby')
        game_state.game_started = False
        return

    # Все игроки готовы начать игру (флаг устанавливается в лобби)
    if all([DataPacket.FLAG_READY in player.flags for player in game_state.players.values()]) \
            and not game_state.game_ended and len(game_state.players) > 1:
        game_state.game_ended = True
        game_state.game_started = True
        await asyncio.sleep(1)
        await change_level('firstmap')
        return

    # В живых остался только один (не единственный) игрок
    if len(game_state.players) > 1 and len(game_state.players_alive) == 1 and not game_state.game_ended:
        game_state.game_ended = True
        game_statistics[game_state.players_alive.pop()]['win'] += 1
        await asyncio.sleep(1)
        if game_state.level_id == GameState.MAX_LEVELS:
            await end_game(len(game_state.players.keys()))
        else:
            await change_level('firstmap')
        return

    for weapon_id in game_state.weapons.keys():
        game_state.weapons[weapon_id].update(time_delta, game_state.level)

    # Пробегаемся по все игрокам
    for client_id in id_to_stream.keys():

        # Игрок выпал за пределы карты
        if client_id in game_state.players.keys() and game_state.players[client_id].y > 3000:
            if game_state.players[client_id].hp == 0:
                continue
            game_state.players[client_id].death()
            data_packet = DataPacket(DataPacket.HEALTH_POINTS, game_state.players[client_id].hp)
            await send(client_id, data_packet)

    # noinspection PyShadowingNames
    async def delete_bullet(bullet_id):  # Рассылает всем пакет, о том, что пуля с id=bullet_id удалена
        if bullet_id not in game_state.bullets.keys():
            return
        game_state.bullets.pop(bullet_id)
        for client_id in id_to_stream.keys():
            data_packet = DataPacket(DataPacket.DELETE_BULLET_FROM_SERVER, bullet_id)
            await send(client_id, data_packet)

    for bullet_id in list(game_state.bullets):
        bullet = game_state.bullets[bullet_id]
        bullet.update(time_delta)

        if bullet.current_lifetime_seconds > bullet.max_lifetime_seconds or \
                game_state.level.collide_point(*bullet.get_position()):
            await delete_bullet(bullet_id)
            continue

        for client_id in id_to_stream.keys():
            if game_state.players[client_id].hp <= 0:
                continue
            if GameState.STATUS_PLAYING not in game_state.players[client_id].flags:
                continue

            if game_state.players[client_id].sprite_rect.collidepoint(bullet.get_position()):
                game_state.players[client_id].take_damage(bullet)

                if game_state.players[client_id].hp <= 0:
                    weapon_id = game_state.players[client_id].weapon_id
                    if weapon_id != -1:
                        weapon = game_state.weapons[weapon_id]
                        weapon_direction = weapon.direction
                        weapon_position = weapon.get_center()
                        weapon_ammo = weapon.ammo
                        game_state.weapons[weapon_id].owner = None
                        game_state.weapons[weapon_id].rect.x, game_state.weapons[weapon_id].rect.y = weapon_position
                        game_state.weapons[weapon_id].direction = weapon_direction
                        response = DataPacket(DataPacket.CLIENT_DROPPED_WEAPON,
                                              {'owner_id': client_id,
                                               'weapon_id': weapon_id,
                                               'weapon_position': weapon_position,
                                               'weapon_direction': weapon_direction,
                                               'weapon_ammo': weapon_ammo})
                        for client_id in id_to_stream.keys():
                            await send(client_id, response)

                data_packet = DataPacket(DataPacket.HEALTH_POINTS, game_state.players[client_id].hp)
                await send(client_id, data_packet)
                await delete_bullet(bullet_id)


async def update_loop():
    last_tick = time.time()
    while True:
        time_delta = time.time() - last_tick
        last_tick = time.time()

        await update(time_delta)
        await asyncio.sleep(1 / TICK_RATE)


async def send_positions_loop(protocol):
    while True:
        for client_id in id_to_udp_address.keys():
            await send_players_data(client_id, protocol)
        await asyncio.sleep(1 / POSITIONS_SEND_RATE)


class UdpServerProtocol(asyncio.DatagramProtocol):
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        data_packet = DataPacket.from_bytes(data)
        client_id = data_packet.headers['id']
        if client_id == -1:
            return
        if data_packet.headers['time'] < id_to_last_udp_packet_time[client_id]:
            return
        id_to_last_udp_packet_time[client_id] = data_packet.headers['time']
        id_to_udp_address[client_id] = addr
        asyncio.get_running_loop().create_task(self.handle(data_packet))

    async def handle(self, data_packet):
        await handle_packet(data_packet)

    def send(self, client_id: int, data_packet: DataPacket):
        data_packet.headers['game_id'] = game_state.level_id
        data_packet.headers['time'] = round(time.time() - start_time, 3)
        self.transport.sendto(data_packet.encode(), id_to_udp_address[client_id])


async def main():
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: UdpServerProtocol(),
        local_addr=(server, udp_port))

    tcp_server = await asyncio.start_server(accept_connection, server, tcp_port)

    print("Server is up waiting...")

    loop_task = asyncio.create_task(update_loop())
    send_positions_task = asyncio.create_task(send_positions_loop(protocol))

    await loop_task
    await send_positions_task
    async with tcp_server:
        await tcp_server.serve_forever()

    return


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.set_debug(DEBUG)
    loop.run_until_complete(main())
    loop.run_forever()
