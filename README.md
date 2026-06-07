# ROFL Player Stats Parser

League of Legends `.rofl` 리플레이 파일에서 플레이어별 챔피언, KDA, 챔피언 대상 딜량, DPM을 추출하는 Python 스크립트입니다.

## 주요 기능

- `.rofl` 파일에서 `statsJson` 메타데이터 추출
- 플레이어별 Riot ID 출력
  - 예: `라니의 파닥몬#진화가능`
- 챔피언명 출력
  - 기본값: 영어 챔피언 ID
  - Data Dragon 사용 시: 한글 챔피언명
- KDA 계산
- 챔피언 대상 총 딜량 출력
- DPM 계산
  - `TOTAL_DAMAGE_DEALT_TO_CHAMPIONS / 게임 시간(분)`

## 필요 환경

Python 3.10 이상을 권장합니다.

별도 `pip install`은 필요하지 않습니다.

사용하는 모듈은 모두 Python 기본 모듈입니다.

```python
from pathlib import Path
import json
from typing import Any
from urllib.request import urlopen
```

## 파일 구조 예시

```text
project/
├─ rofl.py
└─ README.md
```

## 사용 방법

`rofl.py` 파일의 맨 아래에서 `.rofl` 파일 경로를 실제 경로로 수정합니다.

```python
if __name__ == "__main__":
    rofl_file = r"C:\Users\Robin\Documents\League of Legends\Replays\KR-6377066293.rofl"

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
```

그다음 터미널에서 실행합니다.

```bash
python rofl.py
```

## 출력 예시

```text
케 이#999 룰루 1/7/6 3853 137.3
르블랑King#KR1 말파이트 4/1/18 18491 659.0
윤계상#GOD 피들스틱 8/1/11 25168 897.0
나는상헌이#123 사일러스 7/2/16 22993 819.5
Schneider#kr99 진 15/4/10 36612 1304.8
```

## 반환 데이터 예시

`read_rofl_player_stats()` 함수는 아래와 같은 딕셔너리 리스트를 반환합니다.

```python
[
    {
        "summoner_name": "라니의 파닥몬#진화가능",
        "champion": "룰루",
        "kills": 1,
        "deaths": 7,
        "assists": 6,
        "kda": "1/7/6",
        "kda_ratio": 1.0,
        "damage_to_champions": 3853,
        "dpm": 137.3,
        "team": "100",
        "win": False,
    }
]
```

## 챔피언 한글명 변환

챔피언 한글명은 Riot Data Dragon의 `ko_KR/champion.json` 데이터를 사용합니다.

```python
champion_map = load_ko_champion_map()
stats = read_rofl_player_stats(rofl_file, champion_map=champion_map)
```

인터넷 연결이 되지 않으면 한글 챔피언명 변환이 실패할 수 있습니다.

그 경우 아래처럼 `champion_map` 없이 실행하면 영어 챔피언 ID로 출력됩니다.

```python
stats = read_rofl_player_stats(rofl_file)
```

## 주의사항

`.rofl` 파일은 Riot에서 공식적으로 공개한 안정적인 문서화 포맷이 아닙니다.

따라서 LoL 클라이언트 버전, 패치 버전, 리플레이 저장 방식에 따라 다음 문제가 생길 수 있습니다.

- `statsJson`이 비어 있음
- 메타데이터 구조가 다름
- 일부 키 이름이 다름
- 오래된 리플레이 파일을 현재 클라이언트에서 재생할 수 없음

특히 `statsJson`이 비어 있는 `.rofl` 파일은 이 스크립트만으로 챔피언, KDA, 딜량을 추출할 수 없습니다.

## 자주 발생하는 오류

### `NameError: name '_to_float' is not defined`

`_to_float()` 함수가 파일에 없거나, `if __name__ == "__main__":` 실행 코드보다 아래에 있는 경우입니다.

모든 함수 정의를 먼저 작성하고, 실행 코드는 파일 맨 아래에 두세요.

### 챔피언명이 영어로 나오는 경우

실행부에서 `champion_map`을 넘기지 않은 경우입니다.

```python
champion_map = load_ko_champion_map()
stats = read_rofl_player_stats(rofl_file, champion_map=champion_map)
```

### `RecursionError`가 나는 경우

`_get_champion_name()` 함수 안에서 자기 자신을 다시 호출하고 있을 가능성이 큽니다.

아래처럼 `_pick()`을 사용해야 합니다.

```python
def _get_champion_name(player, champion_map=None):
    raw_champion = _pick(player, "SKIN", "championName", "champion", "CHAMPION_NAME")
```

## 라이선스

개인 사용 및 학습용으로 자유롭게 사용할 수 있습니다.
