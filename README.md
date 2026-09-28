# 考古学者のためのGIS入門

本リポジトリは、書籍『考古学者のためのGIS入門』のプロジェクトです。書籍、ウェブページ、実習用コードを対応づけ、考古学におけるGISの学習と実践に役立てることを目指します。

## ウェブページ

[考古学者のためのGIS入門：初級編](https://kotdijian.github.io/IntroductionToArchaeoGIS/)

地理空間情報とGISの概要、およびQGISの操作方法を中心に構成するウェブページです。現時点では「はじめに」から第3章までの章・節構成と、その概要を掲載しています。

## Pythonコード

本リポジトリは、書籍とウェブページで言及するPythonコードの公開先です。コードは今後、対応する章・節と結び付けて追加します。

## Pythonの導入とディレクトリ操作

QGISを画面で操作するだけなら、この節の準備は不要です。書籍やウェブページで紹介するPythonコードを、自分のパソコンで実行するための準備を説明します。**現在、このリポジトリにはPythonスクリプトと `requirements.txt` はまだありません。** まずはPythonの導入、作業場所の確認、仮想環境の作成まで進められます。

**GUIとCLIの違い：** GUI（Graphical User Interface）は、画面上のアイコンやメニューをマウス・トラックパッドで操作する方法です。macOSのFinderやWindowsのエクスプローラーでフォルダを開くのが一例です。CLI（Command Line Interface）は、文字の命令（コマンド）を入力して操作する方法です。たとえば、CLIでは `cd` コマンドを使って作業するフォルダを切り替えます。macOSとWindowsはどちらもGUIとCLIを使えます。

macOSの「ターミナル」やWindowsの「PowerShell」は、CLIで操作するためのアプリです。以下のコマンドは、これらの画面に1行ずつ入力し、Returnキー（WindowsではEnterキー）で実行します。フォルダやディレクトリの意味と移動方法は手順2・3で説明します。

`python` や `py` だけを実行して `>>>` が表示された場合は、**Python対話モード**に入っています。この画面では `cd` などのターミナル・PowerShell用コマンドを実行できません。終了して元の画面に戻るには、`>>>` の後で `exit()` と入力しReturn／Enterキーを押します。キー操作なら、**macOSはControl＋D**、**WindowsはCtrl＋Zを押してからEnter**です。終了操作は入力待ちの `>>>` が表示された状態で行います。`>>>` 自体は画面上の目印なので入力しません。詳しくは[Python 3.13の公式説明](https://docs.python.org/3.13/tutorial/interpreter.html)を参照してください。

### 1. Python 3.13をインストールする

この説明では、[既存の実習プロジェクト](https://github.com/kotdijian/ArtefactsOrthoMaker/blob/main/README.md#environment)と同じPython 3.13系を使います。すでに3.13系が入っていて、下記のバージョン確認が通る場合は再インストール不要です。

**macOS：** [Python公式サイト](https://www.python.org/downloads/)からPython 3.13系のmacOS用インストーラを入手して実行します。インストール後、`/Applications/Python 3.13/` にある `Install Certificates.command` も実行します。ターミナルを開き、次を入力して `Python 3.13.x` と表示されることを確認します。

```bash
python3.13 --version
```

**Windows：** [Python公式サイト](https://www.python.org/downloads/)からPython Install Managerをインストールします。スタートメニューからPowerShellを開き、Python 3.13を導入して確認します。

```powershell
py install 3.13
py -3.13 --version
```

`py` が見つからない場合は、Python Install Managerの導入後にPowerShellを開き直してください。詳しくは[Python公式のWindows向け説明](https://docs.python.org/3/using/windows.html)を参照してください。

### 2. プロジェクトのフォルダを手元に置く

[このリポジトリ](https://github.com/kotdijian/IntroductionToArchaeoGIS)の「Code」→「Download ZIP」で一式をダウンロードし、ZIPを展開します。ダウンロード先が通常の「ダウンロード」フォルダなら、展開後のフォルダ名は一般に `IntroductionToArchaeoGIS-main` です。別の場所に保存した場合や、Gitで複製した場合は名前と場所が異なります。

**ディレクトリはフォルダのこと**です。展開したフォルダの一番上を、このプロジェクトの「ルートディレクトリ」と呼びます。現時点の主なファイルは次のとおりです。

```text
IntroductionToArchaeoGIS-main/
├── README.md     ← いま読んでいる説明
├── LICENSE       ← ライセンス全文
├── index.html    ← ウェブページ
└── style.css     ← ウェブページの見た目
```

後で作る `.venv/` は自分のパソコン内の作業用フォルダです。GitHubにアップロードする対象ではありません。

### 3. ターミナルで「いまいるディレクトリ」を確認する

ターミナルには**現在の作業ディレクトリ**があり、コマンドは通常そこを基準に動きます。`cd` はその場所を切り替えるコマンドです。`cd` を実行してもファイルそのものが移動するわけではありません。

| したいこと | macOSのターミナル | Windows PowerShell |
|---|---|---|
| 現在の場所を表示 | `pwd` | `Get-Location` |
| その場所のファイルとフォルダを表示 | `ls` | `Get-ChildItem` |
| 別のフォルダへ移動 | `cd フォルダ名` | `cd フォルダ名` |
| 一つ上のフォルダへ戻る | `cd ..` | `cd ..` |
| 自分のホームフォルダへ戻る | `cd ~` | `cd ~` |

例えば「ダウンロード」フォルダに展開した場合、次のようにプロジェクトのルートへ移動します。

macOS：

```bash
cd ~/Downloads/IntroductionToArchaeoGIS-main
pwd
ls
```

Windows PowerShell：

```powershell
cd "$HOME\Downloads\IntroductionToArchaeoGIS-main"
Get-Location
Get-ChildItem
```

最後の一覧に `README.md` と `index.html` があれば、正しい場所にいます。見つからなければ実際に展開したフォルダを探して、その場所へ `cd` してください。名前に空白を含むパスは、Windowsの例のように引用符で囲みます。macOSでは、ターミナルに `cd ` と入力してからFinderのフォルダを画面へドラッグすると、そのフォルダのパスを入力できます。

`..` は一つ上のディレクトリ、`.` は現在のディレクトリ、`~` は自分のホームディレクトリを表します。例えばルートにいるときの `README.md` は、その場所にあるファイルを指す**相対パス**です。`/Users/.../README.md` や `C:\Users\...\README.md` のように先頭から場所を指定するものを**絶対パス**と呼びます。コマンドが「ファイルが見つからない」と言うときは、まず現在地とファイル一覧を確認してください。

### 4. プロジェクト専用の仮想環境を作る

仮想環境は、このプロジェクトで使うPythonと追加パッケージを他のプロジェクトから分けるためのディレクトリです。**必ず前節で確認したルートディレクトリに移動してから**、次を実行します。`.venv` の先頭の点は名前の一部で、macOSでは通常、隠しフォルダとして扱われます。

macOS：

```bash
python3.13 -m venv .venv
source .venv/bin/activate
python --version
python -m pip --version
python -c 'print("Python OK")'
```

Windows PowerShell：

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python --version
python -m pip --version
python -c "print('Python OK')"
```

行頭に `(.venv)` が表示され、`Python 3.13.x` と `Python OK` が出れば準備完了です。`pip` はPythonの追加パッケージを入れる道具で、`python -m pip` と書くと、いま選んでいるPython環境の `pip` を使えます。

PowerShellで `Activate.ps1` の実行が制限された場合は、設定を変更せず、仮想環境内のPythonを直接指定して確認できます。

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m pip --version
```

作業を終えるときは `deactivate` で仮想環境を抜けます。ターミナルを閉じても `.venv/` は残ります。次回はプロジェクトのルートへ `cd` してから、有効化の行（macOSでは `source ...`、Windowsでは `Activate.ps1`）だけをもう一度実行します。

### 5. Pythonコードが追加されたら

現在は `requirements.txt` がないため、別のプロジェクトの依存パッケージ一覧を流用したり、`pip install -r requirements.txt` を実行したりしないでください。コードが追加された際には、必要なファイルと実行コマンドを各章・節に記載します。`requirements.txt` が置かれた場合は、仮想環境を有効にし、ルートディレクトリで次を実行します。

```bash
python -m pip install -r requirements.txt
python -m pip check
```

仮想環境の作成と有効化の仕組みは、[Python公式ドキュメント](https://docs.python.org/3.13/library/venv.html)でも確認できます。

## ライセンス

本リポジトリで公開するコードおよび付随する文書は、MITライセンスで提供します。著作権表示は `Copyright (c) 2026 Atsushi Noguchi` です。正式な許諾条件の全文は [LICENSE](LICENSE) を参照してください。

MITライセンスの主な内容は次のとおりです。

- 利用者は、無償で利用、複製、改変、結合、公開、配布、再許諾、販売できます。
- 複製物またはソフトウェアの重要な部分には、著作権表示と許諾表示を含める必要があります。
- ソフトウェアは「現状有姿」で提供されます。商品性、特定目的への適合性、権利非侵害性を含む保証はなく、著作者や著作権者は利用に関連して生じる請求・損害等について責任を負いません。
