# 法律查询助手 V3.4

一个可本地运行的 Flask + SQLite 多法律、版本化法律查询工程。

主要功能：

- 条文号、标题、正文、关键词和编章搜索
- 全部法律跨库搜索，或限定单部法律
- 多部法律统一管理
- 同一法律多个版本并存及现行版本切换
- 现行有效、尚未生效、已失效、已废止等效力状态
- 版本历史浏览与逐条版本差异比较
- 指定日期查询当时适用的已导入版本
- 新旧版本逐字增删高亮
- 正文法律引用自动跨法律跳转
- 本机收藏夹、最近浏览记录和浏览次数
- 自然资源业务专题流程导航
- 官方来源只读更新检查与人工复核记录
- 关联条文和跨版本保留的个人笔记
- 条文页支持键盘 `←` / `→` 切换上一条、下一条
- JSON 批量导入与旧数据库自动迁移

工程已包含从国家法律法规数据库、自然资源部和最高人民法院官网获取并验证的民法典及自然资源行政法律专题库。专题库包括：

- 土地管理法、土地管理法实施条例、城乡规划法
- 行政许可法、行政处罚法、行政复议法、行政诉讼法
- 不动产登记暂行条例、闲置土地处置办法、自然资源行政处罚办法
- 行政诉讼法司法解释、国有土地使用权合同纠纷司法解释、房屋登记案件规定

数据库共含14部法律文件（含民法典），专题库的历史版与现行版合计21个版本。

## V3.4 使用提示

- 查询页的日期框可按行为发生日检索；系统从本地已导入版本中选择该日之前最新、且未超过失效日期的版本。
- 条文页中的明确引用（如“《中华人民共和国民法典》第五百四十五条”）会自动生成跨库链接。
- “业务专题”按工作环节提供检索入口，不代替案件事实审查或正式法律意见。
- “更新检查”只读访问官方来源，发现异常后提示人工复核，不会自动覆盖法条或笔记。
- 收藏、历史、笔记和更新检查结果都保存在 `instance/mfd.sqlite3`，请定期备份该文件。

## 1. 安装与运行

### Windows

最简单的方式：双击 `启动民法典助手.cmd`。首次运行会自动创建环境并安装依赖，随后打开浏览器。停止服务可双击 `停止民法典助手.cmd`。

也可以在 Windows PowerShell 中手动运行：

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

浏览器打开：<http://127.0.0.1:5000>

数据库位于 `instance/mfd.sqlite3`。旧版单法律数据库首次启动时会自动迁移，原条文和笔记均保留。

### Linux 本机运行

适用于 Ubuntu、Debian、统信 UOS、银河麒麟及其他提供 Python 3.10 以上版本的常见发行版。Debian/Ubuntu 系首次使用可安装基础环境：

```bash
sudo apt update
sudo apt install -y python3 python3-venv
```

解压工程后执行：

```bash
chmod +x start-linux.sh stop-linux.sh
./start-linux.sh
```

浏览器打开 <http://127.0.0.1:5000>。停止服务：

```bash
./stop-linux.sh
```

首次启动会在工程目录创建 `.venv` 并安装依赖。日志位于 `instance/server.log` 和 `instance/server-error.log`，数据库仍位于 `instance/mfd.sqlite3`。

从 GitHub 新克隆的工程不会包含个人 SQLite 数据库。第一次启动时，程序会使用仓库内经过校验的官方 JSON 自动建立完整法律库；个人笔记、收藏、历史和检查记录不会上传到 GitHub。

可通过环境变量改变监听地址和端口：

```bash
MFD_HOST=0.0.0.0 MFD_PORT=8080 ./start-linux.sh
```

仅在可信内网中开放监听地址；对公网提供服务时应使用下方的 Gunicorn、Nginx、身份认证和 HTTPS 方案。

## 2. 更新民法典官方文本

```powershell
.venv\Scripts\python.exe tools\import_official_civil_code.py
.venv\Scripts\python.exe -m flask --app app import-json data\civil_code_1260_official.json
```

下载脚本只有在条文号连续为1—1260且正文均非空时才生成导入文件；来源信息和文件 SHA-256 写入 `data/civil_code_source.json`。

更新并重新导入自然资源行政法律专题库：

```powershell
.venv\Scripts\python.exe tools\import_official_collection.py --import-db
```

该脚本会校验标题、条文连续性、正文非空及官方目录条文数；任何空版本或断号版本都会被拒绝导入。下载文件、来源元数据、SHA-256 和导入清单位于 `data/legal_collection/`。

## 3. 导入其他法律及版本

准备一份法律版本元数据和一份条文 JSON，可参考 `data/law_metadata.example.json`：

```powershell
.venv\Scripts\python.exe -m flask --app app import-law `
  data\土地管理法_元数据.json `
  data\土地管理法_条文.json
```

默认将导入版本设为现行版本。导入旧版本时使用：

```powershell
.venv\Scripts\python.exe -m flask --app app import-law 旧版元数据.json 旧版条文.json --historical
```

笔记绑定“法律＋条文号”，升级版本时不会丢失；正文、辅助标题、编章及关联条文绑定具体版本。

条文 JSON 格式：

```json
[
  {
    "article_no": 1,
    "title": "辅助标题",
    "content": "条文原文……",
    "book": "第一编",
    "chapter": "第一章",
    "keywords": ["关键词"],
    "related_articles": [2, 3]
  }
]
```

也支持以条文号为键的对象格式，以及字段别名 `number`、`text`、`related`。

## 4. 效力状态

元数据中的 `status` 和 `version_status` 支持：

- `effective`：现行有效
- `not_effective`：尚未生效
- `expired`：已失效
- `repealed`：已废止
- `unknown`：效力待核

效力状态属于法律数据，应以制定机关或国家法律法规数据库公布的信息为准。

## 5. 运行测试

```powershell
python -m pip install pytest
pytest -q --basetemp=.pytest-tmp
```

## 6. 工程结构

```text
mfd-assistant-v3.1/
├─ app.py                     查询、法律库、版本与比较路由
├─ db.py                      数据库迁移及法律版本导入
├─ schema.sql                 laws / law_versions / articles / notes
├─ start-linux.sh             Linux 一键启动
├─ stop-linux.sh              Linux 安全停止
├─ requirements-linux.txt     Gunicorn 生产依赖
├─ deploy/linux/              systemd 与 Nginx 示例
├─ data/                      法律条文、来源及元数据
├─ tools/                     官方数据获取与校验脚本
├─ static/style.css
├─ templates/
└─ tests/test_app.py
```

## 7. Linux systemd 生产部署

安装生产依赖：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-linux.txt
```

工程提供两个示例文件：

- `deploy/linux/legal-assistant.service.example`
- `deploy/linux/nginx.conf.example`

将工程放到 `/opt/legal-assistant`，修改 service 文件中的用户、组和 `MFD_SECRET_KEY`，再安装服务：

```bash
sudo cp deploy/linux/legal-assistant.service.example /etc/systemd/system/legal-assistant.service
sudo systemctl daemon-reload
sudo systemctl enable --now legal-assistant
sudo systemctl status legal-assistant
```

Nginx 示例需要按实际域名修改，并应同时配置 HTTPS。SQLite 数据库目录必须允许 service 中指定的用户写入；升级前请备份 `instance/mfd.sqlite3`。

## 8. 生产使用提醒

当前版本定位为单机个人工具。若部署到公网，应更换 `MFD_SECRET_KEY`、关闭 debug、增加身份认证和 CSRF 防护，并使用正式 WSGI 服务器。
