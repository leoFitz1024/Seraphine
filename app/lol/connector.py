import subprocess
import re
import os
import json
import requests
import time

from ..common.config import cfg, Language
from .exceptions import *

requests.packages.urllib3.disable_warnings()


def retry(count=5, retry_sep=0.5):

    def decorator(func):

        def wrapper(*args, **kwargs):
            for _ in range(count):
                try:
                    res = func(*args, **kwargs)
                except:
                    time.sleep(retry_sep)
                    continue
                else:
                    break
            else:
                raise Exception("Exceeded maximum retry attempts.")

            return res

        return wrapper

    return decorator


class LolClientConnector():

    def __init__(self):
        self.port = None
        self.token = None
        self.url = None

        self.manager = None

    def start(self):
        command = "wmic process WHERE name='LeagueClientUx.exe' GET commandline"
        output = subprocess.check_output(command).decode('gbk')

        self.port = re.findall(r'--app-port=(.+?)"', output)[0]
        self.token = re.findall(r'--remoting-auth-token=(.+?)"', output)[0]

        self.url = f'https://riot:{self.token}@127.0.0.1:{self.port}'
        self.__initManager()

    def close(self):
        self.__init__()

    @retry()
    def __initManager(self):
        items = self.__get('/lol-game-data/assets/v1/items.json').json()
        spells = self.__get(
            '/lol-game-data/assets/v1/summoner-spells.json').json()
        runes = self.__get('/lol-game-data/assets/v1/perks.json').json()
        queues = self.__get('/lol-game-queues/v1/queues').json()
        champions = self.__get(
            '/lol-game-data/assets/v1/champion-summary.json').json()
        skins = self.__get('/lol-game-data/assets/v1/skins.json').json()

        self.manager = JsonManager(items, spells, runes, queues, champions,
                                   skins)

    @retry()
    def getRuneIcon(self, runeId):
        if runeId == 0:
            return 'app/resource/images/rune-0.png'

        icon = f'app/resource/game/rune icons/{runeId}.png'
        if not os.path.exists(icon):
            path = self.manager.getRuneIconPath(runeId)
            res = self.__get(path)

            with open(icon, 'wb') as f:
                f.write(res.content)

        return icon

    @retry()
    def getCurrentSummoner(self):
        res = self.__get("/lol-summoner/v1/current-summoner").json()

        if not 'summonerId' in res:
            raise Exception()

        return res

    @retry()
    def getInstallFolder(self):
        res = self.__get("/data-store/v1/install-dir").json()
        return res

    @retry()
    def getProfileIcon(self, iconId):
        icon = f"./app/resource/game/profile icons/{iconId}.jpg"

        if not os.path.exists(icon):
            path = self.manager.getSummonerProfileIconPath(iconId)
            res = self.__get(path)
            with open(icon, 'wb') as f:
                f.write(res.content)

        return icon

    @retry()
    def getItemIcon(self, iconId):
        if iconId == 0:
            return 'app/resource/images/item-0.png'

        icon = f'app/resource/game/item icons/{iconId}.png'

        if not os.path.exists(icon):
            path = self.manager.getItemIconPath(iconId)
            res = self.__get(path)

            with open(icon, 'wb') as f:
                f.write(res.content)

        return icon

    @retry()
    def getSummonerSpellIcon(self, spellId):
        if spellId == 0:
            return 'app/resource/images/spell-0.png'

        icon = f'app/resource/game/summoner spell icons/{spellId}.png'

        if not os.path.exists(icon):
            path = self.manager.getSummonerSpellIconPath(spellId)
            res = self.__get(path)

            with open(icon, 'wb') as f:
                f.write(res.content)

        return icon

    @retry()
    def getChampionIcon(self, championId):
        if championId == -1:
            return 'app/resource/images/champion-0.png'

        icon = f'app/resource/game/champion icons/{championId}.png'

        if not os.path.exists(icon):
            path = self.manager.getChampionIconPath(championId)
            res = self.__get(path)

            with open(icon, 'wb') as f:
                f.write(res.content)

        return icon

    def getSummonerByName(self, name):
        params = {'name': name}
        res = self.__get(f"/lol-summoner/v1/summoners", params).json()

        if 'errorCode' in res:
            raise SummonerNotFoundError()

        return res

    @retry()
    def getSummonerByPuuid(self, puuid):
        res = self.__get(f"/lol-summoner/v2/summoners/puuid/{puuid}").json()

        if 'errorCode' in res:
            raise SummonerNotFoundError()

        return res

    @retry()
    def getSummonerGamesByPuuid(self, puuid, begIndex=0, endIndex=4):
        params = {'begIndex': begIndex, 'endIndex': endIndex}
        res = self.__get(f'/lol-match-history/v1/products/lol/{puuid}/matches',
                         params).json()

        if 'games' not in res:
            raise SummonerGamesNotFound()

        return res['games']

    @retry()
    def getGameDetailByGameId(self, gameId):
        res = self.__get(f"/lol-match-history/v1/games/{gameId}").json()

        return res

    @retry()
    def getRankedStatsByPuuid(self, puuid):
        res = self.__get(f"/lol-ranked/v1/ranked-stats/{puuid}").json()

        return res

    @retry()
    def setProfileBackground(self, skinId):
        data = {
            'key': 'backgroundSkinId',
            'value': skinId,
        }
        res = self.__post('/lol-summoner/v1/current-summoner/summoner-profile',
                          data=data).json()

        return res

    @retry()
    def setOnlineStatus(self, message):
        data = {"statusMessage": message}
        res = self.__put("/lol-chat/v1/me", data=data).json()

        return res

    @retry()
    def setTierShowed(self, queue, tier, division):
        data = {
            "lol": {
                "rankedLeagueQueue": queue,
                "rankedLeagueTier": tier,
                "rankedLeagueDivision": division
            }
        }

        res = self.__put("/lol-chat/v1/me", data=data).json()

        return res

    @retry()
    def removeTokens(self):
        data = {"challengeIds": []}
        # data = {"hello": []}
        res = self.__post("/lol-challenges/v1/update-player-preferences/",
                          data=data).content
        return res

    @retry()
    def create5v5PracticeLobby(self, lobbyName, password):
        data = {
            "customGameLobby": {
                "configuration": {
                    "gameMode": "PRACTICETOOL",
                    "gameMutator": "",
                    "gameServerRegion": "",
                    "mapId": 11,
                    "mutators": {
                        "id": 1
                    },
                    "spectatorPolicy": "AllAllowed",
                    "teamSize": 5,
                },
                "lobbyName": lobbyName,
                "lobbyPassword": password,
            },
            "isCustom": True,
        }
        res = self.__post("/lol-lobby/v2/lobby", data=data).json()

        return res

    @retry()
    def setOnlineAvailability(self, availability):
        data = {'availability': availability}

        res = self.__put("/lol-chat/v1/me", data=data)
        return res

    @retry()
    def acceptMatchMaking(self):
        res = self.__post("/lol-matchmaking/v1/ready-check/accept")
        return res

    def selectChampion(self, championId):
        session = self.__get("/lol-champ-select/v1/session").json()
        localPlayerCellId = session['localPlayerCellId']

        for action in session['actions'][0]:
            if action['actorCellId'] == localPlayerCellId:
                id = action['id']
                break

        data = {
            'championId': championId,
        }

        self.__patch(f"/lol-champ-select/v1/session/actions/{id}", data=data)

        self.__post(f"/lol-champ-select/v1/session/actions/{id}/complete",
                    data=data)

    @retry()
    def getSummonerById(self, summonerId):
        res = self.__get(f"/lol-summoner/v1/summoners/{summonerId}").json()

        return res

    def __get(self, path, params=None):
        url = self.url + path
        return requests.get(url, params=params, verify=False)

    def __post(self, path, data=None):
        url = self.url + path
        headers = {'Content-type': 'application/json'}
        return requests.post(url, json=data, headers=headers, verify=False)

    def __put(self, path, data=None):
        url = self.url + path
        return requests.put(url, json=data, verify=False)

    def __patch(self, path, data=None):
        url = self.url + path
        return requests.patch(url, json=data, verify=False)


class JsonManager():

    def __init__(self, itemData, spellData, runeData, queueData, champions,
                 skins):
        self.items = {item['id']: item['iconPath'] for item in itemData}
        self.spells = {item['id']: item['iconPath'] for item in spellData[:-3]}
        self.runes = {item['id']: item['iconPath'] for item in runeData}

        champs = {item['id']: item['name'] for item in champions}

        self.champions = {item: {'skins': {}} for item in champs.values()}

        self.queues = {
            item['id']: {
                'mapId': item['mapId'],
                'name': item['name']
            }
            for item in queueData
        }

        for item in skins.values():
            championId = item['id'] // 1000
            self.champions[champs[championId]]['skins'][
                item['name']] = item['id']
            self.champions[champs[championId]]['id'] = championId

    def getItemIconPath(self, iconId):
        if iconId != 0:
            return self.items[iconId]
        else:
            return '/lol-game-data/assets/ASSETS/Items/Icons2D/gp_ui_placeholder.png'

    def getSummonerSpellIconPath(self, spellId):
        if spellId != 0:
            return self.spells[spellId]
        else:
            return '/lol-game-data/assets/data/spells/icons2d/summoner_empty.png'

    def getRuneIconPath(self, runeId):
        return self.runes[runeId]

    def getSummonerProfileIconPath(self, iconId):
        return f"/lol-game-data/assets/v1/profile-icons/{iconId}.jpg"

    def getChampionIconPath(self, championId):
        return f'/lol-game-data/assets/v1/champion-icons/{championId}.png'

    def getMapNameById(self, mapId):
        maps = {
            -1: ("特殊地图", "Special map"),
            11: ("召唤师峡谷", "Summoner's Rift"),
            12: ("嚎哭深渊", "Howling Abyss"),
            21: ("极限闪击", "Nexus Blitz"),
            30: ("斗魂竞技场", "Arena")
        }

        key = mapId if mapId in maps else -1
        index = 1 if cfg.language.value == Language.ENGLISH else 0

        return maps[key][index]

    def getNameMapByQueueId(self, queueId):
        if queueId == 0:
            return {
                'name':
                "Custom" if cfg.language.value == Language.ENGLISH else '自定义'
            }

        data = self.queues[queueId]
        mapId = data['mapId']
        name = data['name']

        if cfg.language.value == Language.ENGLISH:
            with open("app/resource/i18n/gamemodes.json",
                      encoding='utf-8') as f:
                translate = json.loads(f.read())
                name = translate[name]

        map = self.getMapNameById(mapId)

        return {'map': map, 'name': name}

    def getMapIconByMapId(self, mapId, win):
        result = 'victory' if win else 'defeat'
        if mapId == 11:
            mapName = 'sr'
        elif mapId == 12:
            mapName = 'ha'
        elif mapId == 30:
            mapName = 'arena'
        else:
            mapName = 'other'

        return f'app/resource/images/{mapName}-{result}.png'

    def getChampionList(self):
        return [item for item in self.champions.keys()]

    def getSkinListByChampionName(self, championName):
        try:
            return [item for item in self.champions[championName]['skins']]
        except:
            return []

    def getSkinIdByChampionAndSkinName(self, championName, skinName):
        return self.champions[championName]['skins'][skinName]

    def getChampionIdByName(self, championName):
        return self.champions[championName]['id']