# midea_flowchart

美的暖通/楼宇控制 JSON 程序流程图生成工具。

## 当前能力

- 解析 `programs` 下的图形流程序 JSON，输出统一中间模型：
  `tabs`、`subflows`、`subflow_instances`、`quotes`、`points`、`edges`。
- 将 `文档/1.命名规则v20191011B.XLSX` 编译为运行时索引：
  `data/naming_rules.sqlite` 和 `data/naming_rules.json`。
- 对所有示例 JSON 生成验收报告：
  `build/acceptance_report.md` 和 `build/acceptance_report.json`。
- 将节点级程序压缩为模块级抽象图数据：
  `build/diagrams/*.json` 和 `build/diagram_report.md`。

## 运行

```powershell
conda activate midea
python -m midea_flowchart.cli accept --programs programs --excel "文档/1.命名规则v20191011B.XLSX" --data-dir data --out build
python -m midea_flowchart.cli build-diagrams --programs programs --rules-json data/naming_rules.json --profiles configs/domain_profiles --out build/diagrams
```

## 测试

```powershell
conda activate midea
python -m unittest discover -v
```
