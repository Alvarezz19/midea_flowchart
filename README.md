# midea_flowchart

美的暖通/楼宇控制 JSON 程序流程图生成工具。

本项目的目标是读取 `programs` 目录下的图形化控制程序 JSON，将原始节点级程序解析、命名校验、抽象压缩，并最终以可交互流程图展示给用户。当前重点不是复刻所有底层节点，而是生成“用户能看懂、工程人员能追溯”的模块级流程图。

## 当前状态

已完成三部分基础能力：

- **统一解析**：解析 `tab`、`subflow`、子流程实例、点位、引用和连线，输出中间模型。
- **命名索引**：将 `文档/1.命名规则v20191011B.XLSX` 编译为运行时索引，避免每次查询都读取 Excel。
- **抽象图与前端**：将节点级程序压缩为模块级图数据，并用 React + React Flow 做本地交互原型。

当前已覆盖 `programs` 下 5 个 JSON 项目：

- AHU 程序：三山经开区、云霞县华龙科技、泰安宁阳中医院
- 机房群控程序：群控示例程序、风冷热泵标准控制程序

## 数据流程

```text
programs/*.json
  -> midea_flowchart.flow_parser
  -> build/intermediate/*.json
  -> midea_flowchart.diagram_builder
  -> build/diagrams/*.json
  -> web/public/data/*
  -> React Flow 前端展示
```

命名规则流程：

```text
文档/1.命名规则v20191011B.XLSX
  -> data/naming_rules.sqlite
  -> data/naming_rules.json
  -> 点位命名匹配、未匹配标记、模块风险提示
```

## 目录结构

```text
midea_flowchart/              Python 工具包
  flow_parser.py              JSON 统一解析
  naming_rules.py             命名规则索引编译与匹配
  xlsx_reader.py              标准库 XLSX 读取
  diagram_builder.py          模块级抽象图生成
  acceptance.py               全量验收报告
  cli.py                      命令行入口

configs/domain_profiles/      领域抽象配置
  ahu.json
  chiller_plant.json
  air_source_heat_pump.json

programs/                     原始项目 JSON
文档/                         命名规则和结构分析文档
data/                         命名规则运行时索引
build/                        解析结果、抽象图、验收报告
web/                          React + React Flow 前端原型
tests/                        回归与验收测试
```

## 后端生成

在 Windows PowerShell 中执行：

```powershell
conda activate midea
python -m midea_flowchart.cli accept --programs programs --excel "文档/1.命名规则v20191011B.XLSX" --data-dir data --out build
python -m midea_flowchart.cli build-diagrams --programs programs --rules-json data/naming_rules.json --profiles configs/domain_profiles --out build/diagrams
```

生成结果：

- `data/naming_rules.sqlite`
- `data/naming_rules.json`
- `build/acceptance_report.md`
- `build/acceptance_report.json`
- `build/intermediate/*.json`
- `build/diagrams/*.json`
- `build/diagram_report.md`
- `build/diagram_report.json`

## 前端原型

前端使用 `React + Vite + @xyflow/react + lucide-react`。

```powershell
cd web
npm install
npm run dev
```

默认地址：

```text
http://127.0.0.1:5173/
```

前端启动前会自动执行：

```powershell
npm run prepare:data
```

该脚本会把 `build/diagrams/*.json` 同步到 `web/public/data/`，并生成 `web/public/data/manifest.json`。

生产构建：

```powershell
cd web
npm run build
```

## 测试

```powershell
conda activate midea
python -m unittest discover -v
```

当前测试覆盖：

- 5 个项目 JSON 是否能解析为统一模型
- 命名规则 Excel 是否能编译为 SQLite/JSON 索引
- 全量验收报告是否通过
- 抽象图是否能为所有项目生成，并控制页面模块数量

## 当前验收结果

最近一次验收结果：

- 命名规则：`633` 条规则，`3038` 条别名索引
- 项目数量：`5`
- 所有项目 `quote` 回溯率：`100%`
- 抽象图验收：通过
- 前端构建：通过

抽象图示例指标：

- 三山 AHU：总览 `4` 个模块、`3` 条总览边，控制页由 `327` 个原始节点压缩为 `19` 个模块
- 风冷热泵标准程序：总览 `9` 个模块、`24` 条总览边，最大页面模块数 `18`

## 设计原则

- **通用解析优先**：不能只服务三山 AHU，所有 JSON 都必须走同一解析管线。
- **领域配置抽象**：AHU、机房群控、风冷热泵使用不同 `domain_profile` 做模块归类。
- **规则确定性优先**：点位解析、命名匹配、连线聚合以确定性规则为主。
- **AI 辅助而非替代**：后续 AI 更适合生成模块摘要、解释未匹配点位、建议抽象粒度，不应直接决定底层图结构。
- **可追溯**：每个抽象模块保留 `source_node_ids`，能回到原始 JSON 节点。

## 下一步建议

1. 在前端补充未匹配点位完整列表，而不只是样例。
2. 给模块增加 AI 摘要占位字段，并设计结构化输出格式。
3. 用甲方关注的三山 AHU 对照 `示例.png` 做一次视觉和抽象粒度评审。
4. 根据评审反馈调整 `configs/domain_profiles/*.json`，而不是硬编码在前端。
5. 增加导出 PNG/SVG/PDF 能力，方便交付评审。
