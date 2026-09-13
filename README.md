# 甯у奖 FrameCraft

![Build](https://github.com/jrangus/FrameCraft-Windows/actions/workflows/release-windows.yml/badge.svg)

甯у奖鏄竴娆鹃潰鍚?Windows 10/11 64 浣嶇郴缁熺殑渚挎惡瑙嗛鍘熷甯у鍑哄伐鍏枫€傚畠鐩存帴淇濆瓨瑙嗛瑙ｇ爜鍚庣殑褰撳墠甯э紝涓嶆埅鍙栧睆骞曪紝涔熶笉浼氭妸缂╂斁鍚庣殑棰勮鍥惧綋浣滄埅鍥句繚瀛樸€?
## 涓嬭浇

鍓嶅線 [Releases](https://github.com/jrangus/FrameCraft-Windows/releases/latest) 涓嬭浇 `甯у奖-FrameCraft-Windows渚挎惡鐗?zip`锛岃В鍘嬪悗鍙屽嚮 `甯у奖 FrameCraft.exe`銆?
澶嶅埗鍒板叾浠栫數鑴戞椂璇峰鍒舵暣涓В鍘嬬洰褰曪紝涓嶈鍙鍒?EXE銆?
## 鍔熻兘

- 鎵撳紑鎴栨嫋鍏?MP4銆丮KV銆丮OV銆丄VI銆乄ebM 绛夊父瑙佽棰戙€?- 鏃堕棿杞村畾浣嶃€侀€愬抚鍓嶅悗绉诲姩銆佸墠鍚庤烦杞竴绉掋€?- 鎸夊師濮嬪儚绱犲昂瀵稿鍑?PNG銆乀IFF 鎴?BMP銆?- 鏈湴鏅鸿兘绛涢€夋渶澶?8 涓簿褰╁抚鍊欓€夛紝涓嶄笂浼犺棰戙€佷笉闇€瑕?API銆?- 绮鹃€夊抚绠＄悊鍣ㄦ彁渚涘ぇ鍥炬煡鐪嬨€佸嬀閫夈€佸叏閫夈€佹壒閲忎繚瀛樸€佺Щ闄ゃ€佹竻绌哄拰閲嶆柊鍒嗘瀽銆?- 鐐瑰嚮鍊欓€夊抚鍙細鍒囨崲澶у浘涓庝富绐楀彛棰勮锛屽€欓€夊垪琛ㄤ笉浼氫涪澶憋紱鍏抽棴鍚庡彲鍐嶆鎵撳紑銆?- 鏀寔涓枃鏂囦欢鍚嶅拰涓枃璺緞锛岃嚜甯﹀紑婧愪腑鏂囧瓧浣撱€?
## 鐣岄潰

![涓荤獥鍙(docs/main-window.png)

![绮鹃€夊抚绠＄悊鍣╙(docs/candidate-manager.png)

## 蹇嵎閿?
| 蹇嵎閿?| 鍔熻兘 |
| --- | --- |
| `Ctrl+O` | 鎵撳紑瑙嗛 |
| `Ctrl+S` | 淇濆瓨褰撳墠甯?|
| `Space` | 鎾斁鎴栨殏鍋?|
| `鈫恅 / `鈫抈 | 涓婁竴甯?/ 涓嬩竴甯?|
| `Shift+鈫恅 / `Shift+鈫抈 | 鍓嶅悗璺宠浆涓€绉?|

## 浠庢簮浠ｇ爜杩愯

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe framecraft.py
```

鏋勫缓渚挎惡鐗堬細

```powershell
.\build_portable.ps1
```

## 鈥滄棤鎹熲€濈殑杈圭晫

PNG銆乀IFF銆丅MP 淇濆瓨杩囩▼涓笉浼氬啀娆℃崯澶卞儚绱狅紝瀵煎嚭灏哄涓庡綋鍓嶈棰戣В鐮佸抚涓€鑷淬€傝棰戝鏋滃師鏈娇鐢?H.264銆丠.265 绛夋湁鎹熺紪鐮侊紝杞欢鏃犳硶鎭㈠缂栫爜涔嬪墠宸茬粡涓㈠け鐨勭粏鑺傘€傚綋鍓嶇増鏈潰鍚戝父瑙?8-bit SDR 瑙嗛锛汬DR/10-bit 涓撲笟鑹插僵宸ヤ綔娴佸皻鏈敮鎸併€?
## 闅愮涓?AI

瑙嗛鍜屾櫤鑳界瓫閫夎繃绋嬪叏閮ㄥ湪鏈満瀹屾垚銆傚綋鍓嶇簿褰╁抚绛涢€夌患鍚堟竻鏅板害銆佹洕鍏夈€佸姣斿害銆侀ケ鍜屽害鍜岀敾闈㈠彉鍖栵紝涓嶈皟鐢ㄤ簯绔?AI API銆?
## 绗笁鏂圭粍浠?
椤圭洰浣跨敤 PySide6銆丱penCV銆丯umPy锛屽苟闅忕▼搴忓垎鍙?Noto Sans CJK SC 瀛椾綋銆傚瓧浣撹鍙瘉瑙?[`assets/Noto-CJK-LICENSE.txt`](assets/Noto-CJK-LICENSE.txt)銆?
