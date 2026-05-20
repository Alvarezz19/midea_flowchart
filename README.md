# 美的暖通流程图生成工具

本项目用于解析美的暖通/楼宇控制平台导出的 JSON 程序，并生成更适合工程阅读的流程图视图。

系统不直接复刻原始编程平台画布，而是把原始节点和连线转换为“工程逻辑说明图 + 原始节点可追溯”的多层视图，帮助管理人员、暖通工程人员和程序调试人员从不同粒度理解项目。

## 主要能力

- 读取示例项目、上传 JSON 或粘贴 JSON。
- 自动识别项目 profile，例如 AHU、机房群控、风冷热泵。
- 生成系统总览图，展示页签和模块之间的工程关系。
- 生成模块详情图，展示页签内部的业务模块和数据流。
- 保留原始节点图，用于追踪节点、连线和点位来源。
- 对点位命名进行规则匹配，展示匹配、未匹配和冲突状态。
- 支持直膨机状态矩阵展示。
- 支持导出后端生成的 project view JSON。

## 设计思路

项目采用三层视图：

1. 系统总览图：面向甲方、管理人员和工程负责人，强调系统结构。
2. 模块详情图：面向暖通/楼控工程人员，强调控制模块、输入输出和业务链路。
3. 原始节点图：面向程序开发和调试人员，保留原始 JSON 的追溯能力。

后端负责解析、命名匹配和抽象图构建；前端只负责展示和交互。

## 快速开始

在 Windows 终端中进入项目根目录后执行：

```powershell
conda activate midea
python -m midea_flowchart.server --host 127.0.0.1 --port 8765
```

然后在浏览器打开：

```text
http://127.0.0.1:8765
```

页面启动后可以选择内置示例项目，也可以上传或粘贴美的平台导出的 JSON。

## 常用命令

运行测试：

```powershell
conda activate midea
python -m unittest discover -s tests
```

检查 Python 模块能否正常编译：

```powershell
conda activate midea
python -m compileall midea_flowchart
```

导出某个项目的中间视图 JSON：

```powershell
conda activate midea
python scripts/export_project_view.py "programs/AHU程序/三山经开区/flows_20251210190941.json" -o output/project_view.json
```

验证 profile JSON 格式：

```powershell
conda activate midea
python -m json.tool configs/domain_profiles/ahu.json
```

## 目录概览

- `midea_flowchart/`：后端 Python 包。
- `web/`：前端页面和原生 ES module。
- `configs/domain_profiles/`：领域 profile 配置。
- `data/`：命名规则数据。
- `programs/`：示例项目 JSON。
- `scripts/`：辅助脚本。
- `tests/`：测试。
- `文档/`：原始资料和分析文档。
- `记录/`：设计方案和开发记录。
- `output/`：导出样例。

更详细的维护边界见根目录 [项目结构.md](项目结构.md)。

## 当前实现边界

- 当前重点支持 AHU 程序，并保留机房群控、风冷热泵等非 AHU 项目的通用降级展示。
- profile 可配置页签角色、点位分组、总览图规则和详情图声明式规则。
- 点位和子流程实例的复杂启发式分类仍在 Python 中实现。
- AI 解释、图纸导出和更完整的按需追踪接口属于后续扩展方向。

## 数据来源

仓库内置样例和规则数据包括：

- `programs/` 下的 AHU、机房群控、风冷热泵程序样例。
- `data/naming_rules.json` 和 `data/naming_rules.sqlite`。
- `文档/1.命名规则v20191011B.XLSX`。
- `configs/domain_profiles/*.json`。

## 维护原则

- 解析层保持通用。
- 抽象层优先通过 profile 配置扩展。
- 展示层只消费后端 project view。
- 未识别内容应可见并可追踪，不应静默丢弃。
