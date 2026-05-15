# car_tool

绠€浣撲腑鏂囪鏄庯紝English summary below.

## 椤圭洰绠€浠?
`car_tool` 鏄竴涓潰鍚戞竻娲佸皬杞︿换鍔′笅鍙戠殑杈呭姪鎶€鑳斤紝鏍稿績鐩爣鏄妸鐢ㄦ埛鐨勮嚜鐒惰瑷€娓呮壂闇€姹傝浆鎹负鍙墽琛屻€佸彲瑙嗗寲銆佸彲杩借釜鐨勫尯鍩熶换鍔°€?

杩欎釜椤圭洰涓昏瑙ｅ喅涓夌被闂锛?
- 浠?39 涓瀹氫箟鍙竻鎵尯鍩熶腑蹇€熺‘瀹氱洰鏍囧尯鍩?
- 缁撳悎 POI 鎼滅储銆佸湴鍥炬埅鍥惧拰鍖哄煙鍖归厤锛岃緟鍔╁垽鏂湴鐐瑰簲钀藉湪鍝釜鍖哄煙
- 鐢熸垚鏍囧噯鍖栦换鍔″弬鏁颁笌浜や簰寮忓湴鍥剧粨鏋滐紝鏂逛究浜哄伐纭鍜屽悗缁嚜鍔ㄥ寲澶勭悊

鎹㈠彞璇濊锛屽畠涓嶆槸涓€涓崟绾殑鈥滄煡鍦板浘鈥濆伐鍏凤紝鑰屾槸涓€濂楀洿缁曟竻娲佷换鍔¤鍒掋€佸尯鍩熺‘璁ゅ拰缁撴灉灞曠ず鐨勫伐浣滄祦銆?

## 閫傜敤鍦烘櫙
- 鐢ㄦ埛鍙鈥滄竻鎵煇涓湴鐐归檮杩戔€濓紝闇€瑕佸厛鎶婂湴鐐规槧灏勫埌鍖哄煙缂栧彿
- 鐢ㄦ埛缁欏嚭澶氫釜鍦扮偣锛岄渶瑕佸垽鏂槸杩炵画璺緞杩樻槸骞跺垪浠诲姟
- 闇€瑕佺敓鎴愬甫 POI 鏍囪鐨勫湴鍥炬埅鍥撅紝杈呭姪瑙嗚纭
- 闇€瑕佹妸鏈€缁堜换鍔＄粨鏋滀繚瀛樺埌鐙珛鐨?session 鐩綍涓紝渚夸簬杩借釜鍜屽鐢?

## 鏍稿績鑳藉姏
- 39 涓彲娓呮壂鍖哄煙鐨勪换鍔℃槧灏勪笌鍖哄煙閫夋嫨
- POI 鎼滅储涓庡湴鐐瑰潗鏍囪幏鍙栵紝瑙?[scripts/poi_search.js](scripts/poi_search.js)
- 鍦板浘鎴浘鐢熸垚锛岃 [scripts/map_screenshot.py](scripts/map_screenshot.py)
- 鍖哄煙鍙鍖栦笌璺緞灞曠ず锛岃 [scripts/visualize_regions.py](scripts/visualize_regions.py)
- 宸茬煡鍦版爣鏌ヨ涓庝换鍔′細璇濈鐞嗭紝瑙?[scripts/preset_scripts.py](scripts/preset_scripts.py) 鍜?[scripts/session_manager.py](scripts/session_manager.py)

## 宸ヤ綔娴佺▼
1. 瑙ｆ瀽鐢ㄦ埛杈撳叆锛岃瘑鍒崟鐐广€佽矾寰勩€佸鐐规垨缁勫悎浠诲姟
2. 浼樺厛鏌ヨ宸茬煡鍦版爣锛屽垽鏂槸鍚﹁兘鐩存帴鏄犲皠鍒板尯鍩熺紪鍙?
3. 瀵规湭鐭ュ湴鏍囨墽琛?POI 鎼滅储锛岃幏鍙栧潗鏍囧苟鐢熸垚鍦板浘鎴浘
4. 缁撳悎鍖哄煙杈圭晫銆佽瑙夌粨鏋滄垨璺濈瑙勫垯锛岀‘璁ゆ渶缁堟竻鎵尯鍩?
5. 淇濆瓨浠诲姟鍙傛暟锛屽苟鐢熸垚鍙鍖栫粨鏋滅敤浜庢鏌ュ拰灞曠ず

## 鐩綍璇存槑
- [scripts/](scripts/)锛氭牳蹇冭剼鏈洰褰曪紝鍖呭惈 POI 鎼滅储銆佹埅鍥俱€佸彲瑙嗗寲鍜屼細璇濈鐞嗛€昏緫
- [docs/](docs/)锛氫娇鐢ㄨ鏄庡拰琛ュ厖鏂囨。
- [references/](references/)锛氬弬鑰冭祫鏂欏拰绠楁硶璇存槑
- [evals/](evals/)锛氳瘎娴嬮厤缃?
- [examples/](examples/)锛氱ず渚嬭皟鐢ㄦ柟寮?

## 浣跨敤璇存槑
### 1. 杩涘叆鑴氭湰鐩綍

```bash
cd c:\Users\18325\.claude\skills\car-tool\scripts
```

### 2. 鐢熸垚鍖哄煙鍙鍖?

```bash
python visualize_regions.py 0 1 2 --no-open
```

### 3. 鏌ヨ鍦版爣鎴栫敓鎴愪换鍔?

鍏蜂綋璋冪敤鏂瑰紡浠?[docs/USAGE.md](docs/USAGE.md) 鍜屽悇鑴氭湰澶撮儴娉ㄩ噴涓哄噯銆備笉鍚屼换鍔＄被鍨嬩細璧颁笉鍚屽垎鏀紝閫氬父涓嶉渶瑕佹墜宸ユ嫾鎺ユ墍鏈変腑闂翠骇鐗┿€?

## 閰嶇疆鏂囦欢
- [scripts/config.json](scripts/config.json)锛氫换鍔′笅鍙戜笌杩愯閰嶇疆
- [scripts/known_landmarks.json](scripts/known_landmarks.json)锛氬凡鐭ュ湴鏍囦笌鍖哄煙鏄犲皠
- [scripts/rectangles.json](scripts/rectangles.json)锛氬尯鍩熻竟鐣屼笌甯冨眬鏁版嵁

## GitHub 鍙戝竷
濡傛灉闇€瑕佹妸褰撳墠浠撳簱鎺ㄩ€佸埌 GitHub锛屽彲浠ユ寜甯歌娴佺▼鎵ц锛?

```bash
git init
git add .
git commit -m "Refine car_tool documentation"
git branch -M main
git remote add origin https://github.com/kuinooos/wuyuanbay-pathfinding-skill.git
git push -u origin main
```

濡傛灉浠撳簱宸茬粡瀛樺湪杩滅锛屽彧闇€瑕佸湪鏈湴鎻愪氦鍚庢墽琛?`git push` 鍗冲彲銆?

## English Summary
`car_tool` is a workflow-oriented skill for cleaning-task dispatch. It helps map natural-language cleaning requests to one of 39 predefined regions, uses POI search and map screenshots when a location is not already known, and produces task parameters plus visual output for review and execution.
