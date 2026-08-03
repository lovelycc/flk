"""Curated navigation for common natural-resources legal workflows.

The topics point to searches instead of duplicating legal conclusions. This
keeps the official article text as the source of truth while still offering a
practical path through each workflow.
"""

TOPICS = [
    {
        "slug": "illegal-land-use",
        "title": "违法用地查处",
        "summary": "从线索核查、立案调查到处罚执行与救济的办案导航。",
        "laws": ["land-administration-law", "administrative-penalty-law", "natural-resources-administrative-penalty-measures"],
        "steps": [
            ("线索核查", "监督检查 违法占地"),
            ("立案与管辖", "立案 管辖"),
            ("调查取证", "调查取证"),
            ("陈述申辩与听证", "陈述申辩 听证"),
            ("处罚决定与送达", "处罚决定 送达"),
            ("履行与强制执行", "强制执行"),
            ("复议与诉讼", "行政复议 行政诉讼"),
        ],
    },
    {
        "slug": "idle-land",
        "title": "闲置土地认定与处置",
        "summary": "围绕调查、认定、处置方案、信息公开和权利救济组织依据。",
        "laws": ["idle-land-disposal-measures", "land-administration-law"],
        "steps": [
            ("启动调查", "涉嫌构成闲置土地"),
            ("调查与认定", "闲置土地调查认定"),
            ("原因区分", "政府原因 开发建设"),
            ("处置方案", "处置方案 闲置费 收回"),
            ("告知与送达", "告知 送达"),
            ("信息公开和监管", "信息公开 监管"),
            ("复议与诉讼", "行政复议 行政诉讼"),
        ],
    },
    {
        "slug": "land-expropriation",
        "title": "土地征收",
        "summary": "梳理公共利益、前期工作、补偿安置、批准实施与争议救济。",
        "laws": ["land-administration-law", "land-administration-law-regulations"],
        "steps": [
            ("公共利益与范围", "公共利益 征收"),
            ("预公告与现状调查", "征收土地预公告 现状调查"),
            ("社会稳定风险评估", "社会稳定风险评估"),
            ("补偿安置方案", "征地补偿安置方案"),
            ("听证与协议", "听证 补偿登记 协议"),
            ("报批与公告", "征收土地申请 公告"),
            ("补偿争议救济", "征地补偿 行政复议"),
        ],
    },
    {
        "slug": "construction-land-approval",
        "title": "建设用地审批",
        "summary": "覆盖农用地转用、土地征收、供地和批后监管的检索入口。",
        "laws": ["land-administration-law", "land-administration-law-regulations", "urban-rural-planning-law"],
        "steps": [
            ("规划与计划", "国土空间规划 土地利用年度计划"),
            ("农用地转用", "农用地转用 审批"),
            ("土地征收", "征收土地 审批"),
            ("供地方式", "划拨 出让 建设用地"),
            ("规划许可", "建设用地规划许可证"),
            ("批后监管", "批准用途 监督检查"),
        ],
    },
    {
        "slug": "temporary-land-use",
        "title": "临时用地",
        "summary": "查询临时用地审批、期限、复垦和违法责任。",
        "laws": ["land-administration-law", "land-administration-law-regulations"],
        "steps": [
            ("适用范围", "临时使用土地"),
            ("审批与合同", "临时用地 批准 合同"),
            ("使用期限", "临时用地 期限"),
            ("复垦义务", "土地复垦"),
            ("违法责任", "临时用地 法律责任"),
        ],
    },
    {
        "slug": "real-estate-registration",
        "title": "不动产登记",
        "summary": "围绕申请、受理、审核、登簿、查询和登记争议组织依据。",
        "laws": ["interim-real-estate-registration-regulations", "spc-house-registration-provisions", "civil-code"],
        "steps": [
            ("登记申请", "不动产登记申请"),
            ("受理与材料", "登记申请材料 受理"),
            ("查验与实地查看", "查验 实地查看"),
            ("登簿与发证", "登记簿 权属证书"),
            ("更正与异议登记", "更正登记 异议登记"),
            ("资料查询", "登记资料查询"),
            ("登记行政诉讼", "房屋登记 行政诉讼"),
        ],
    },
    {
        "slug": "planning-permits",
        "title": "城乡规划许可",
        "summary": "建设项目选址、用地、工程和乡村建设规划许可导航。",
        "laws": ["urban-rural-planning-law", "administrative-licensing-law"],
        "steps": [
            ("规划依据", "控制性详细规划"),
            ("选址与用地许可", "选址意见书 建设用地规划许可证"),
            ("工程规划许可", "建设工程规划许可证"),
            ("乡村建设许可", "乡村建设规划许可证"),
            ("规划核实", "规划条件 核实"),
            ("违法建设处理", "未取得建设工程规划许可证"),
        ],
    },
    {
        "slug": "administrative-remedies",
        "title": "行政复议与行政诉讼",
        "summary": "按期限、管辖、受理、审理和裁判梳理行政争议救济路径。",
        "laws": ["administrative-reconsideration-law", "administrative-litigation-law", "spc-administrative-litigation-interpretation"],
        "steps": [
            ("救济方式选择", "行政复议 行政诉讼"),
            ("申请或起诉期限", "申请期限 起诉期限"),
            ("管辖与被申请人", "管辖 被申请人 被告"),
            ("受理条件", "受理条件"),
            ("证据与举证责任", "证据 举证责任"),
            ("决定与裁判", "复议决定 判决"),
            ("执行与监督", "执行 监督"),
        ],
    },
]

TOPIC_BY_SLUG = {topic["slug"]: topic for topic in TOPICS}
