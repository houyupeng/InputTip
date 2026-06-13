# 本 fork 的个人定制说明

这个 fork 主要记录一组本机使用的 InputTip 定制方案。原项目仍然是 `abgox/InputTip`，本文件只说明当前分支上相对上游的个人改动和本机配置。

## 1. 鼠标样式定制

目标是保留 InputTip 通过“状态提示 - 鼠标样式”实现的实时性，同时让鼠标视觉更接近 Windows 原生光标。

当前本机使用的方案是：

- 从 `C:\Windows\Cursors` 读取 Windows 原生光标作为基础形状。
- 生成三套本地主题：
  - `native-color-red`：中文状态。
  - `native-color-blue`：英文状态和 US 键盘。
  - `native-color-green`：CapsLock 状态。
- 普通箭头、手型、IBeam、十字、上箭头等可见区域统一填充为对应状态色。
- 禁止、移动、缩放等依赖内部负形识别的光标保留白色镂空。
- IBeam 文本输入光标额外加粗，方便在输入区域识别中英状态。

生成脚本：

```powershell
python .\tools\make-native-color-cursors.py --output-root .\src\data\cursor
```

脚本会在 `src\data\cursor` 下生成本地主题目录。`src\data` 属于运行时数据目录，不建议提交生成后的 `.cur` 文件；这些文件来自本机 Windows 系统光标资源的派生结果。

本机当前配置示例：

```ini
cursorActive="1"
overlayActive="0"
cursorPathCN="native-color-red"
cursorPathEN="native-color-blue"
cursorPathCaps="native-color-green"
cursorPathUS="native-color-blue"
```

## 2. 自动更新

本机为了避免手动定制被自动更新覆盖，关闭了 InputTip 启动时检查更新：

```ini
checkUpdateOnStartup="0"
```

这是本机运行配置，不建议作为上游默认行为提交。需要更新 InputTip 时，应先备份或重新生成本地鼠标主题，再手动迁移配置。

## 3. 已提交到分支的内容

当前分支提交的是：

- 生成原生统一色彩鼠标主题的脚本：`tools/make-native-color-cursors.py`
- 个人定制说明：`CUSTOMIZATION.zh-CN.md`
- 早前用于试验的 IBeam-only 内置主题分支内容

生成后的 `native-color-*` 光标主题和 `src\data\config.ini` 保持为本机文件，不随 Git 提交。
