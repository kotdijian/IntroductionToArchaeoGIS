# 地理院DEMの変換と結合

国土地理院の基盤地図情報「数値標高モデル」（DEM）を、QGISの外で一括処理するスクリプトです。入力フォルダに置いたGML形式のXMLファイル（または国土地理院から取得した各メッシュのZIPファイル）を標高値入りのGeoTIFFに変換し、一枚の `dem_merged.tif` に結合します。入力ファイルは変更しません。

## 準備

Pythonの導入とターミナル／PowerShellの基本操作は[リポジトリのREADME](../README.md#pythonの導入とディレクトリ操作)を参照してください。プロジェクトのルートで仮想環境を有効にしてから、このフォルダへ移動します。

```bash
cd GML-DEMmerge
python -m pip install -r requirements.txt
```

macOSでは `source .venv/bin/activate`、Windowsでは `.\.venv\Scripts\Activate.ps1` を**プロジェクトのルート**で実行すると、上記の `python` が仮想環境のPythonになります。PowerShellで有効化できないときは、ルートから `.\.venv\Scripts\python.exe -m pip install -r GML-DEMmerge\requirements.txt` と入力し、実行時には `..\.venv\Scripts\python.exe dem_merge.py` を使えます。

## 入力ファイル

このフォルダに `inputGML` フォルダを作り、対象地域のXMLまたは**各メッシュごとのZIP**を直接入れます。両方を重複して入れないでください。まとめてダウンロードした外側のZIPに複数のZIPが入っている場合は、外側だけを展開し、中の各メッシュのZIPを置きます。

```text
GML-DEMmerge/
├── dem_merge.py
├── requirements.txt
├── inputGML/                    ← 自分で作成し、ダウンロードしたデータを入れる
│   ├── FG-GML-533952-DEM10B-20260901.zip
│   └── FG-GML-533953-DEM10B-20260901.zip
└── output/                      ← 実行後に作成される
    ├── dem_merged.tif          ← 結合したDEM
    └── tiles/                  ← メッシュごとのGeoTIFF
```

上のファイル名と日付は配置例です。実際に国土地理院から取得したファイルを使ってください。10m DEMは6桁の2次メッシュ番号、1m・5m DEMのXMLは8桁の3次メッシュ番号で確認します。ZIPの名前は2次メッシュ番号で、その中に1m・5mの3次メッシュXMLが複数入ることがあります。

## 実行

`GML-DEMmerge` に移動した状態で、次を実行します。

```bash
python dem_merge.py
```

作業中の場所を基準に `inputGML` を読み、`output/tiles/` に各メッシュのGeoTIFF、`output/dem_merged.tif` に結合結果を作ります。QGISでは `dem_merged.tif` をラスタレイヤとして開きます。再実行時に前回の `output/tiles` や `output/dem_merged.tif` がある場合は停止します。必要な結果を別の場所へ退避してから再実行してください。

別の入力・出力フォルダを指定する場合：

```bash
python dem_merge.py --input "/path/to/my-dem" --output "/path/to/my-output"
```

パスは自分のパソコンの実際の場所に置き換えます。Windowsの例は `--input "C:\Users\名前\Documents\inputGML"` です。空白を含む場所は引用符で囲みます。

### 欠けたメッシュの確認

スクリプトは作業開始前に、ファイル名とGML内の番号が一致するか、格子間隔の混在、番号の重複、離れたメッシュや囲まれた欠落がないかを確かめます。JGD2011とJGD2024の標高が混在した場合も停止します。エラーが出たら入力ファイルを確認し、そろえてから再実行してください。

**外周のメッシュが丸ごと一つ欠けていても、残ったファイル名だけでは欠落を判断できません。** 範囲を確実に確認するときは、国土地理院のダウンロード画面で選んだメッシュ番号を1行ずつ記したUTF-8のテキストファイルを作り、指定します。10m DEMなら6桁、1m・5m DEMなら8桁の番号です。

```text
533952
533953
```

```bash
python dem_merge.py --expected-meshes expected_meshes.txt
```

一覧と入力が一致しなければ、不足または余分な番号を表示して停止します。範囲が辺でつながらない場合や、海岸・提供範囲の都合でデータのない地域メッシュを含む場合は、対象を分けて実行してください。ファイル名の検査だけで、**各メッシュ内に標高値がくまなくあること**までは保証できません。

## 座標と標高について

出力GeoTIFFには水平位置の参照として `EPSG:6668` を付け、元のGMLに記された `JGD2011` または `JGD2024` を `GSI_VERTICAL_DATUM` という付加情報にも保存します。JGD2024への移行で水平位置の緯度・経度は変更されていませんが、標高の基準は改定されています。このスクリプトは標高の補正、別の座標系への変換、解像度の変更を行いません。異なる標高基準のファイルは一緒に結合しないでください。

## 国土地理院の測量成果の利用

入力のGML、およびそれを変換・結合したGeoTIFFは国土地理院の基盤地図情報を利用した測量成果です。[国土地理院コンテンツ利用規約](https://www.gsi.go.jp/kikakuchousei/kikakuchousei40182.html)と[基盤地図情報ダウンロードサービスの利用案内](https://service.gsi.go.jp/kiban/app/help/)に従い、利用目的に応じた複製・使用承認の要否を確認してください。出典と加工した事実も記載してください。

**GMLや結合したGeoTIFFを、国土地理院の承認を得ずにこの公開リポジトリへ置かないでください。** GeoTIFFへ変換しても再配布に当たる点は変わりません。原データと出力はローカルで管理します。リポジトリのMITライセンスはここで公開するコード・説明文に適用され、国土地理院のデータにMITライセンスを付けるものではありません。公開を検討するときは、国土地理院の[測量成果の複製・使用申請](https://www.gsi.go.jp/LAW/2930-index.html)で条件を確認してください。

仕様・操作の参照先：[国土地理院のDEMの種類と配布単位](https://service.gsi.go.jp/kiban/app/help/)、[国土地理院FAQのファイル名と格子の説明](https://www.gsi.go.jp/kiban/faq.html)。
