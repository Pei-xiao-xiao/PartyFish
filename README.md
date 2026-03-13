# PartyFish

PartyFish 是一个面向《Party Animals》钓鱼玩法的 Windows 桌面辅助工具。  
项目基于图像识别、OCR 和输入模拟实现自动化钓鱼，并提供记录、收益、图鉴、放生和悬浮窗等配套功能。

## 说明

- 仅支持 Windows 10 / 11
- 推荐 Python 3.11
- 当前仓库以源码运行和 Windows 打包为主，不提供跨平台支持
- 当前项目为源码公开（source-available），不是 OSI 定义的 open source
- 这是一个自动化工具，使用前请自行评估相关平台或游戏规则带来的风险

## 功能概览

- 自动钓鱼流程：自动抛竿、等待咬钩、收线、继续下一轮
- 鱼获记录：通过 OCR 识别鱼名、品质、重量并写入本地 CSV
- 收益统计：记录卖鱼收入、鱼饵消耗和每日收益
- 图鉴功能：查看鱼类数据、收集进度、筛选条件和详情信息
- 放生策略：支持关闭、单条放生、桶满自动放生
- 截图支持：支持 WeGame 保存截图，也支持 Steam `F12`
- 悬浮窗：显示运行状态、销售进度、鱼类预览和 UNO 状态
- 多账号：按账号隔离记录、销售数据、图鉴进度和部分设置
- 热键与手柄：支持全局热键和手柄映射

## 运行环境

运行依赖定义在 [pyproject.toml](pyproject.toml)。

主要依赖包括：

- `PySide6`
- `PySide6-Fluent-Widgets`
- `opencv-python`
- `mss`
- `rapidocr-onnxruntime`
- `pynput`
- `pygame`
- `wmi`

## 快速开始

### 1. 创建环境

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e .[dev]
```

### 2. 运行程序

```powershell
python main.py
```

如果全局热键、键鼠模拟或窗口激活不生效，优先尝试以管理员身份运行终端或程序。

## 测试与检查

```powershell
python -m pytest tests -q
python -m py_compile main.py build.py src\gui\main_window.py src\inputs.py src\services\fishing_service.py src\workers.py
```

如果你启用了 pre-commit，也可以执行：

```powershell
pre-commit run --all-files
```

## 打包

项目当前使用 [build.py](build.py) + [PartyFish.spec](PartyFish.spec) 进行 PyInstaller 打包。

先安装 PyInstaller：

```powershell
python -m pip install -e ".[build]"
```

然后执行：

```powershell
python build.py
```

打包结果会输出到 `dist/` 目录，构建脚本会按版本整理可执行文件和附带资源。

## 数据目录

运行时数据默认保存在：

```text
%APPDATA%\Partyfish
```

主要文件结构如下：

```text
%APPDATA%\Partyfish\
├─ config.json
└─ accounts\
   └─ <账号名>\
      ├─ account_settings.json
      ├─ pokedex.json
      └─ data\
         ├─ records.csv
         └─ sales.csv
```

额外输出目录：

- 截图目录：`<程序目录>\截图\`
- 调试截图与日志导出：`<程序目录>\debug_screenshots\`
- 部分运行时截图缓存：`<程序目录>\screenshots\`

仓库内的 [data](data) 目录主要包含：

- [data/protected_fish.json](data/protected_fish.json)：放生保护数据
- [data/audio](data/audio)：提示音资源

## 默认热键

- `F2`：启动 / 暂停自动钓鱼
- `F10`：生成调试截图
- `F4`：卖鱼快捷操作
- `F3`：UNO 功能快捷键

热键和手柄映射都可以在设置页中修改。

## 项目结构

```text
.
├─ main.py
├─ build.py
├─ PartyFish.spec
├─ pyproject.toml
├─ resources/
├─ data/
├─ src/
│  ├─ config.py
│  ├─ inputs.py
│  ├─ vision.py
│  ├─ workers.py
│  ├─ pokedex.py
│  ├─ uno.py
│  ├─ configs/
│  ├─ gui/
│  ├─ managers/
│  └─ services/
└─ tests/
```

几个主要入口：

- [main.py](main.py)：程序入口
- [src/gui/main_window.py](src/gui/main_window.py)：主窗口与页面装配
- [src/workers.py](src/workers.py)：后台工作线程
- [src/services/fishing_service.py](src/services/fishing_service.py)：钓鱼核心逻辑
- [src/config.py](src/config.py)：配置与运行时状态入口

## 常见问题

### 热键按了没有反应

- 先确认程序没有被暂停在后台
- 优先尝试以管理员身份运行
- 如果游戏本身是管理员权限运行，PartyFish 也应使用同级权限

### 截图没有保存

- 检查设置中的截图模式是否与当前平台一致
- `Steam` 模式依赖 `F12`
- `WeGame` 模式会直接保存图片到程序目录下的 `截图` 文件夹

### 识别效果不稳定

- 确认游戏窗口尺寸和缩放状态正常
- 确认资源文件没有缺失
- 使用 `F10` 导出调试截图排查模板匹配区域

## 开发说明

- 代码格式化目前使用 `black`
- 欢迎提交 issue 和 PR，但建议先附带最小复现步骤或调试截图

## 许可证与使用限制

- 当前版本使用 [Commons Clause + Apache 2.0](LICENSE)
- 这意味着源码可查看、可修改、可分发，但不授予出售本软件的权利
- 未经单独书面授权，不得将本项目本体或其主要价值来源于本项目功能的产品/服务用于收费分发、售卖或变相倒卖
- `PartyFish` 名称、Logo、图标、截图素材和其他视觉标识不在软件许可授权范围内，说明见 [NOTICE](NOTICE)
- 如果你要提供商业化发行或商业授权，需要由版权持有人单独授权
