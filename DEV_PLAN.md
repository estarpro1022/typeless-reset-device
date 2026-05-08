# DEV_PLAN.md - Typeless 重置与迁移工具开发计划

## 版本 1.0 - 初始版本 (已完成)
- **TASK001**: 实现 macOS 下的设备 ID 重置逻辑 (Bash)。
- **TASK002**: 逆向 Typeless v1.3.0 的 `electron-store` 加密逻辑。
- **TASK003**: 实现词典 API 的 HMAC-SHA1 签名与加密协议。
- **TASK004**: 编写 `export.py` 和 `import.py` 实现数据迁移。

---

## 版本 2.0 - Windows 支持与跨平台重构 (当前版本)

### TASK001: 跨平台路径与常量适配
- **版本**: 2.0
- **状态**: 已完成
- **描述**: 在 `crypto_utils.py` 中引入 `sys.platform`，自动适配 Windows 和 macOS 的常量。
- **子任务**:
  - [x] 适配 `TYPELESS_DIR` (%APPDATA%\Typeless)。
  - [x] 适配 `platform_str` (win32-x64)。
  - [x] 适配版本前缀 (win_)。
- **验收标准**: Windows 下能正确读取 `user-data.json`。
- **AI 提示词**: (见执行历史)

### TASK002: Windows 设备 ID 获取适配
- **版本**: 2.0
- **状态**: 已完成
- **描述**: 修改 `get_device_id` 以适配 Windows 环境下的凭据获取。
- **子任务**:
  - [x] 适配 Windows `device.cache` 路径。
- **验收标准**: `get_device_id()` 在 Windows 下返回有效 UUID。

### TASK003: 编写统一的跨平台 `reset.py` 脚本
- **版本**: 2.0
- **状态**: 已完成
- **描述**: 使用 Python 替代原有的 bash 脚本，实现一键重置。
- **子任务**:
  - [x] 实现跨平台进程杀灭逻辑。
  - [x] 实现跨平台文件/目录清理。
  - [x] 移除对外部 `node` 命令的依赖。
- **验收标准**: `python reset.py` 在双端均可运行。

### TASK004: 更新文档与 DEV_PLAN.md
- **版本**: 2.0
- **状态**: 进行中
- **描述**: 更新中英文 README 和 GEMINI.md。
- **子任务**:
  - [ ] 编写 `DEV_PLAN.md`。
  - [ ] 更新 `README.md`。
  - [ ] 更新 `README.en.md`。
  - [ ] 更新 `GEMINI.md`。

---

## 版本 3.0 - 功能增强与体验优化 

### TASK001: GUI 界面开发
- **版本**: 3.0
- **状态**: 已完成 (2026-05-07)
- **描述**: 为不熟悉命令行的用户提供图形化操作界面。
- **子任务**:
  - [x] 使用 Tkinter 构建界面。
  - [x] 集成导出、重置、导入的一键工作流。
- **验收标准**: 提供可视化操作窗口，实时显示运行日志。

