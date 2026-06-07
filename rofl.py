from pathlib import Path
import json
from typing import Any
from urllib.request import urlopen


def read_rofl_player_stats(
    rofl_path: str | Path,
    champion_map: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    .rofl 파일에서 플레이어별 챔피언, KDA, DPM, 딜량을 추출한다.

    반환 예:
    [
        {
            "summoner_name": "Hide on bush",
            "champion": "아리",
            "kills": 10,
            "deaths": 2,
            "assists": 8,
            "kda": "10/2/8",
            "kda_ratio": 9.0,
            "damage_to_champions": 30211,
            "dpm": 890.6,
            "team": "100",
            "win": True,
        },
        ...
    ]
    """
    path = Path(rofl_path)
    data = path.read_bytes()

    if data[:4] != b"RIOT":
        raise ValueError("유효한 LoL .rofl 파일이 아닙니다. 파일 시작 시그니처가 RIOT가 아닙니다.")

    metadata = _read_rofl_metadata(data)
    stats_json = _extract_stats_json(metadata)

    game_length_ms = _to_float(metadata.get("gameLength"))
    game_minutes = game_length_ms / 60000 if game_length_ms and game_length_ms > 0 else None

    result: list[dict[str, Any]] = []

    for player in stats_json:
        champion = _get_champion_name(player, champion_map)
        summoner_name = _get_summoner_name(player)


        kills = _to_int(_pick(player, "CHAMPIONS_KILLED", "kills"), 0)
        deaths = _to_int(_pick(player, "NUM_DEATHS", "deaths"), 0)
        assists = _to_int(_pick(player, "ASSISTS", "assists"), 0)

        damage = _to_int(
            _pick(
                player,
                "TOTAL_DAMAGE_DEALT_TO_CHAMPIONS",
                "totalDamageDealtToChampions",
                "damageToChampions",
            ),
            0,
        )

        dpm = round(damage / game_minutes, 1) if game_minutes else None

        if deaths == 0:
            kda_ratio = None  # 노데스는 보통 Perfect로 따로 처리
            kda_display = f"{kills}/0/{assists} Perfect"
        else:
            kda_ratio = round((kills + assists) / deaths, 2)
            kda_display = f"{kills}/{deaths}/{assists}"

        win_raw = _pick(player, "WIN", "win")
        win = None
        if win_raw is not None:
            win = str(win_raw).lower() in ("win", "true", "1")

        result.append(
            {
                "summoner_name": summoner_name,
                "champion": champion,
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "kda": kda_display,
                "kda_ratio": kda_ratio,
                "damage_to_champions": damage,
                "dpm": dpm,
                "team": _pick(player, "TEAM", "teamId", "team"),
                "win": win,
            }
        )

    return result


def _read_rofl_metadata(data: bytes) -> dict[str, Any]:
    """
    알려진 두 가지 .rofl 메타데이터 구조를 순서대로 시도한다.
    1. 최신 계열: 파일 끝 4바이트 = metadata length
    2. 구형 계열: 262바이트 위치에 metadata offset/length 정보 존재
    """
    errors: list[str] = []

    for parser in (_parse_new_tail_metadata, _parse_old_offset_metadata):
        try:
            metadata = parser(data)
            if isinstance(metadata, dict) and ("statsJson" in metadata or "gameLength" in metadata):
                return metadata
        except Exception as e:
            errors.append(f"{parser.__name__}: {e}")

    raise ValueError(
        "이 .rofl 파일에서 메타데이터를 읽지 못했습니다. "
        "패치 버전상 statsJson이 제거되었거나, 지원하지 않는 rofl 구조일 수 있습니다.\n"
        + "\n".join(errors)
    )

def load_ko_champion_map(version: str = "latest") -> dict[str, str]:
    """
    Data Dragon에서 영문 챔피언 ID -> 한글 챔피언명 매핑을 만든다.
    예: Lulu -> 룰루, Malphite -> 말파이트, Fiddlesticks -> 피들스틱
    """
    if version == "latest":
        with urlopen("https://ddragon.leagueoflegends.com/api/versions.json") as res:
            versions = json.loads(res.read().decode("utf-8"))
            version = versions[0]

    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/ko_KR/champion.json"

    with urlopen(url) as res:
        champion_json = json.loads(res.read().decode("utf-8"))

    champion_map: dict[str, str] = {}

    for champ in champion_json["data"].values():
        # id 기준: Ahri, Lulu, Fiddlesticks 등
        champion_map[str(champ["id"]).lower()] = champ["name"]

        # 혹시 key 숫자로 들어오는 경우 대비
        champion_map[str(champ["key"]).lower()] = champ["name"]

        # 한글명이 이미 들어온 경우도 그대로 통과 가능하게
        champion_map[str(champ["name"]).lower()] = champ["name"]

    # .rofl에서 FiddleSticks처럼 대소문자가 다르게 들어오는 경우 대비
    champion_map["fiddlesticks"] = "피들스틱"
    champion_map["fiddlestick"] = "피들스틱"

    return champion_map


def _get_champion_name(player: dict[str, Any], champion_map: dict[str, str] | None = None) -> str | None:
    raw_champion = _pick(player, "SKIN", "championName", "champion", "CHAMPION_NAME")

    if raw_champion is None:
        return None

    raw_champion = str(raw_champion)

    if champion_map is None:
        return raw_champion

    return champion_map.get(raw_champion.lower(), raw_champion)


def _parse_new_tail_metadata(data: bytes) -> dict[str, Any]:
    if len(data) < 8:
        raise ValueError("파일이 너무 작습니다.")

    metadata_length = int.from_bytes(data[-4:], byteorder="little", signed=False)

    if metadata_length <= 0 or metadata_length > len(data) - 4:
        raise ValueError(f"비정상 metadata_length: {metadata_length}")

    start = len(data) - 4 - metadata_length
    raw = data[start : len(data) - 4]

    return json.loads(raw.decode("utf-8"))


def _parse_old_offset_metadata(data: bytes) -> dict[str, Any]:
    file_info_pos = 262
    file_info_len = 26

    if len(data) < file_info_pos + file_info_len:
        raise ValueError("구형 파일 정보 영역을 읽을 수 없습니다.")

    info = data[file_info_pos : file_info_pos + file_info_len]

    metadata_offset = int.from_bytes(info[6:10], byteorder="little", signed=False)
    metadata_length = int.from_bytes(info[10:14], byteorder="little", signed=False)
    payload_header_offset = int.from_bytes(info[14:18], byteorder="little", signed=False)

    candidates: list[bytes] = []

    if 0 <= metadata_offset < payload_header_offset <= len(data):
        candidates.append(data[metadata_offset:payload_header_offset])

    if 0 <= metadata_offset < len(data) and metadata_length > 0:
        candidates.append(data[metadata_offset : metadata_offset + metadata_length])

    last_error: Exception | None = None

    for raw in candidates:
        try:
            text = raw.decode("utf-8").strip("\x00\r\n\t ")
            return json.loads(text)
        except Exception as e:
            last_error = e

    raise ValueError(f"구형 metadata JSON 파싱 실패: {last_error}")


def _extract_stats_json(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    stats = metadata.get("statsJson")

    if isinstance(stats, str):
        stats = stats.strip()

        if not stats or stats == "[]":
            raise ValueError(
                "이 .rofl 파일의 statsJson이 비어 있습니다. "
                "이 경우 챔피언/KDA/딜량을 .rofl만으로 추출할 수 없습니다."
            )

        stats = json.loads(stats)

    if not isinstance(stats, list) or not stats:
        raise ValueError(
            "statsJson이 없거나 비어 있습니다. "
            "패치 버전 또는 리플레이 저장 방식 때문에 메타데이터가 빠졌을 수 있습니다."
        )

    return stats


def _pick(obj: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in obj:
            return obj[key]
    return None

def _get_summoner_name(player: dict[str, Any]) -> str | None:
    game_name = _pick(player, "RIOT_ID_GAME_NAME", "riotIdGameName")
    tag_line = _pick(player, "RIOT_ID_TAG_LINE", "riotIdTagline", "riotIdTagLine")

    if game_name and tag_line:
        return f"{game_name}#{tag_line}"

    if game_name:
        return str(game_name)

    return _pick(player, "NAME", "summonerName", "SUMMONER_NAME")


def _to_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (TypeError, ValueError):
            return default


def _to_float(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
        

if __name__ == "__main__":
    rofl_file = r"C:\Users\Robin\Documents\League of Legends\Replays\KR-8185042674.rofl" #본인의 ROFL 파일의 위치를 올리기 

    champion_map = load_ko_champion_map()
    stats = read_rofl_player_stats(rofl_file, champion_map=champion_map)

    for row in stats:
        print(
            row["summoner_name"],
            row["champion"],
            row["kda"],
            row["damage_to_champions"],
            row["dpm"],
        )