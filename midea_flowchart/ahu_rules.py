from __future__ import annotations

from typing import Any

from .serializers import point_search_text


ROLE_META: dict[str, dict[str, str]] = {
    "io_comm": {"label": "IO/通讯", "kind": "boundary"},
    "control": {"label": "控制", "kind": "control"},
    "schedule": {"label": "定时", "kind": "schedule"},
    "dx_status": {"label": "直膨机状态", "kind": "communication"},
    "dx_fault": {"label": "直膨机故障", "kind": "alarm"},
    "exhaust_fan": {"label": "排风机", "kind": "output"},
    "unknown_tab": {"label": "未识别页签", "kind": "unknown"},
}

AHU_ROLE_ORDER = ["io_comm", "schedule", "dx_status", "control", "exhaust_fan", "dx_fault", "unknown_tab"]

AHU_RELATIONS = [
    ("io_comm", "control", "现场/通讯点位进入控制逻辑"),
    ("schedule", "control", "定时使能参与控制判断"),
    ("dx_status", "control", "直膨机状态反馈参与控制"),
    ("control", "io_comm", "控制结果写回输出和通讯点"),
    ("io_comm", "dx_status", "通讯寄存器支撑直膨状态解析"),
    ("dx_fault", "control", "直膨故障参与联锁保护"),
    ("control", "exhaust_fan", "控制逻辑生成排风机命令"),
]

MODULE_KIND_META: dict[str, dict[str, str]] = {
    "field_input": {"label": "物理输入", "kind": "boundary"},
    "comm_input": {"label": "通讯输入", "kind": "communication"},
    "reference": {"label": "调用信号", "kind": "boundary"},
    "internal": {"label": "点位标准化 / 内部变量", "kind": "internal"},
    "physical_output": {"label": "物理输出", "kind": "output"},
    "comm_output": {"label": "通讯输出", "kind": "communication"},
    "system": {"label": "系统运行 / 故障 / 模式判断", "kind": "control"},
    "schedule_enable": {"label": "定时允许和系统使能", "kind": "schedule"},
    "fan_start": {"label": "送风机启停联锁", "kind": "control"},
    "fan_frequency": {"label": "送风机频率控制", "kind": "algorithm"},
    "temperature": {"label": "温湿度控制", "kind": "algorithm"},
    "valve": {"label": "冷水阀 / 热水阀控制", "kind": "output"},
    "electric_heat": {"label": "电加热 / 电预热控制", "kind": "output"},
    "damper_co2": {"label": "风阀 / CO2 控制", "kind": "control"},
    "dx_control": {"label": "直膨机控制", "kind": "communication"},
    "feedback": {"label": "BACnet / 内部状态反馈", "kind": "internal"},
    "exhaust": {"label": "排风机控制", "kind": "output"},
    "fault": {"label": "故障 / 报警 / 保护", "kind": "alarm"},
    "unclassified": {"label": "未归类逻辑", "kind": "unknown"},
    "timer_input": {"label": "TIME_EN / SP0", "kind": "schedule"},
    "timer_logic": {"label": "与逻辑", "kind": "control"},
    "timer_output": {"label": "TIME_CST", "kind": "output"},
    "dx_register": {"label": "Modbus 状态寄存器", "kind": "communication"},
    "dx_convert": {"label": "直膨状态解析与倍率换算", "kind": "algorithm"},
    "dx_standard": {"label": "标准状态点 / BACnet 点", "kind": "internal"},
}

AHU_CONTROL_MODULE_ORDER = [
    "system",
    "schedule_enable",
    "fan_start",
    "fan_frequency",
    "temperature",
    "valve",
    "electric_heat",
    "damper_co2",
    "dx_control",
    "feedback",
    "fault",
    "unclassified",
]

AHU_IO_MODULE_ORDER = ["field_input", "comm_input", "reference", "internal", "physical_output", "comm_output"]


def classify_control_point(point: Any) -> str:
    text = point_search_text(point)
    group = point.group
    if "TIME" in text or "定时" in group:
        return "schedule_enable"
    if any(token in text for token in ("SYS", "MODE", "运行", "模式", "手自动", "启停")) or "系统" in group:
        return "system"
    if any(token in text for token in ("SF", "送风机")):
        return "fan_frequency" if any(item in text for item in ("FREQ", "HZ", "频率")) else "fan_start"
    if any(token in text for token in ("EF", "RF", "排风机", "回风机")):
        return "exhaust"
    if any(token in text for token in ("SA", "RA", "TEMP", "HUM", "温度", "湿度", "除湿", "加湿")) or "温湿度" in group:
        return "temperature"
    if any(token in text for token in ("CWV", "HWV", "CHV", "阀", "水阀")) or "水阀" in group:
        return "valve"
    if any(token in text for token in ("EH", "EHEAT", "电加热", "电预热")):
        return "electric_heat"
    if any(token in text for token in ("CO2", "FAD", "RAD", "OAD", "DAD", "风阀")):
        return "damper_co2"
    if any(token in text for token in ("ZP", "DX", "EXV", "直膨", "外机", "压缩机")):
        return "dx_control"
    if any(token in text for token in ("FAULT", "ALARM", "故障", "报警", "保护", "滤网")) or "报警" in group:
        return "fault"
    if point.point_kind == "software":
        return "feedback"
    return "unclassified"


def classify_module_instance(name: str, subflow_name: str, tab_role: str) -> str:
    text = f"{name} {subflow_name}".upper()
    if tab_role == "exhaust_fan":
        return "exhaust"
    if "风机" in text:
        return "fan_start"
    if "电加热" in text:
        return "electric_heat"
    if "水阀" in text or "阀" in text:
        return "valve"
    if "CO2" in text or "风阀" in text:
        return "damper_co2"
    return "unclassified"


def module_order_for_control_tab(role: str) -> list[str]:
    if role == "exhaust_fan":
        return ["system", "schedule_enable", "exhaust", "feedback", "fault", "unclassified"]
    if role == "dx_fault":
        return ["dx_control", "fault", "feedback", "unclassified"]
    return AHU_CONTROL_MODULE_ORDER


def control_profile_edges(role: str) -> list[tuple[str, str]]:
    if role == "exhaust_fan":
        return [("system", "exhaust"), ("schedule_enable", "exhaust"), ("exhaust", "feedback")]
    if role == "dx_fault":
        return [("dx_control", "fault"), ("fault", "feedback")]
    return [
        ("system", "schedule_enable"),
        ("schedule_enable", "fan_start"),
        ("fan_start", "fan_frequency"),
        ("system", "temperature"),
        ("temperature", "valve"),
        ("temperature", "electric_heat"),
        ("temperature", "damper_co2"),
        ("dx_control", "feedback"),
        ("fan_start", "feedback"),
    ]


def detail_position(tab_role: str, index: int) -> tuple[int, int]:
    if tab_role == "io_comm":
        positions = [(80, 110), (80, 290), (80, 470), (420, 290), (760, 180), (760, 400)]
        return positions[index] if index < len(positions) else (760, 560 + index * 120)
    if tab_role == "schedule":
        positions = [(120, 260), (470, 260), (820, 260)]
        return positions[index] if index < len(positions) else (820, 420)
    if tab_role == "dx_status":
        positions = [(120, 260), (480, 260), (840, 260)]
        return positions[index] if index < len(positions) else (840, 420)
    if tab_role == "control":
        positions = [
            (60, 92),
            (60, 292),
            (330, 92),
            (600, 92),
            (330, 292),
            (600, 292),
            (870, 292),
            (600, 492),
            (60, 492),
            (870, 92),
            (870, 492),
            (330, 492),
        ]
        return positions[index] if index < len(positions) else (70 + (index % 4) * 270, 540 + (index // 4) * 150)
    x_positions = [70, 350, 630, 910]
    return x_positions[index % len(x_positions)], 110 + (index // len(x_positions)) * 170


def overview_position(profile_name: str, role: str, index: int) -> tuple[int, int]:
    if profile_name == "ahu":
        positions = {
            "io_comm": (90, 260),
            "schedule": (360, 110),
            "dx_status": (360, 410),
            "control": (640, 260),
            "exhaust_fan": (920, 160),
            "dx_fault": (920, 390),
        }
        if role in positions:
            return positions[role]
        return 920, 520 + index * 130
    return 110 + (index % 4) * 280, 120 + (index // 4) * 190
