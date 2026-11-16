# Legacy TNO v2 实测运行报告

本版以 DR11 DECam 的物理曝光为母样本，复用 NOIRLab NSC DR2 的逐 CCD 独立检测。真实源表、每个 CCD 的可用性明细、盲搜成员 ID 和完整中间数据保存在 NERSC scratch。本报告记录已核实的运行结果，并标明尚未验收的范围。

## 数据入口

按 legacypipe DR11.1.0 的 `sefn` 命名规则，在 NERSC 的 DR11 data 和 work 根目录核验五个归档场共 7,446 条唯一 SE 路径。这些路径在本次检查中均缺失。逐场与逐路径统计见 [SE 审计](../results/v2/legacy_se_fields_summary.json) 和 NERSC 的 `v2/legacy_se_fields.json`。[legacypipe DR11.1.0](https://github.com/legacysurvey/legacypipe/blob/DR11.1.0/py/legacypipe/image.py)

通过 NOIRLab Query Client 读取 `nsc_dr2.exposure`、`chip`、`meas`，按 DECam EXPNUM、UTC 曝光起始时刻、波段、曝光时长和 CP 图像 HDU 上的物理 CCD 编号核对。三组归档控制场的 Legacy 曝光与 NSC 匹配分别为 11/11、35/36、38/38。共同 CCD 分别为 670/670、923/928、962/962。归档的两个 2021 年窗口没有 NSC DR2 曝光匹配。该年份缺口保留 SEP 路径和原有实测结果。[曝光审计](../results/v2/nsc_inventory_summary.json) · [CCD 审计](../results/v2/nsc_ccd_summary.json) · [NSC DR2 测量定义](https://datalab.noirlab.edu/data-explorer?showTable=nsc_dr2.meas)

| 控制场 | 实读 NSC 源 | 归一化后保留 | Slurm 归一化 |
|---|---:|---:|---|
| 2013 TV158 | 1,356,317 | 1,351,521 | 61392190，167 s，0:0 |
| 2017 OF201 | 936,200 | 931,799 | 61392191，173 s，0:0 |
| 2013 RD124 / 2013 RQ157 | 621,504 | 619,380 | 61392310，108 s，0:0 |

每组测量返回行数均和 NSC 芯片索引一致。下载以曝光与一至八个 CCD 组为单位缓存，保留测量 ID。适配器采用 CP 的 UTC 起始时刻加半曝光时长，将 NSC 的 AUTO AB 星等转换为纳米马吉，使用 RA、Dec 两个角秒位置误差中较大的值作为共同权重分量。CP 权重、DQ、边缘和 NSC 提源旗标提供质量筛选。按曝光历元传播 Gaia 星表，实测 CCD 偏移与散布。NSC 原有标定位置进入拟合，附加散布下限 0.15″。NSC AUTO 流量和 Sweep PSF 流量的显著超量判定在本版关闭。默认关联输入仅含通过静态与质量筛选且 SNR ≥ 5 的检测，静态歧义检测仍留在分类结果。

## 冻结全池盲搜

| 目标 | A 几何曝光 | B 实测 | C 入池 | D 可关联 | E 盲搜 | 相应距离箱 |
|---|---:|---:|---:|---|---|---|
| 2013 TV158 | 26 | 23 | 23 | 是 | 23 个纯成员，六夜 | 24/24 完成 |
| 2013 TG228 | 3 | 0 | 0 | 否 | 无 | 与 TV158 同一场 |
| 2017 OF201 | 4 | 3 | 3 | 否 | 无 | 9/24 完成 |
| 2013 RD124 | 11 | 0 | 0 | 否 | 无 | 24/24 完成 |
| 2013 RQ157 | 9 | 0 | 0 | 否 | 无 | 与 RD124 同一场 |

表中 A–F 取自盲搜后目标核对。三者均无仅引导拟合成功（F）。表中的 TG228 A 采用 DES 状态和 TAN 足迹判据，独立 Horizons 加 CP WCS 得到四个 CCD 位置，其中两处没有可用的中心像素或产品，两处未在 1.25″ 内检出。TV158 场 923/928 个 CCD 有 NSC 产品，限制来自同一曝光中缺失的五片 CCD。3,861 个干净检测参加匿名关联。单条纯成员链的拟合弧长 31.90 天，东西与南北残差的合并 RMS 为 0.0445″。留出六个整夜时每次由训练位置重新初始化，RMS 为 0.0485–0.0741″。整夜重排通过拟合的链数为 0，无距离箱截断。[TV158 运行记录](../results/v2/tv158/run_manifest.json) · [候选摘要](../results/v2/tv158/candidate_summary.json) · [独立历元审计](../results/v2/nsc-horizons-tv158.json)

OF201 场用于测试四夜门槛。共 23,810 个干净检测也进入了搜索。真实场七条四夜链通过数值拟合，夜重排六条，分别有 15、16 个距离箱触发上限；这些链的身份和图像检查仍待完成。OF201 第四个预期历元为 EXPNUM 759212、N26、z 波段。独立 Horizons W84 星历位置上 CP 中心 DQ 为 0，9×9 像素窗可用比例为 98.8%，最近 NSC 源在 32.66″ 外。同 CCD SEP 对照表明原 v1 检测在 NSC 缺失。该历元无法进入冻结四夜流程，距离箱截断另外记录。盲搜本体写齐结果后，作业 61392252 的 Slurm 文件名解析以 2:0 退出，独立身份后处理由作业 61392263 完成（24 s，0:0）。[OF201 盲搜范围](../results/v2/of201/search_domain_summary.json) · [回收结果](../results/v2/of201/stress_recovery_summary.json) · [独立历元审计](../results/v2/nsc-horizons-of201.json)

原漏检控制场作业 61392388 完成（280 s，0:0）。5,289 个干净检测参加盲搜，主搜索和夜重排均无截断或通过拟合的链。DES 状态预测的 11 个 RD124 和 9 个 RQ157 覆盖曝光内均无 NSC 匹配检测。该场的独立 Horizons 像素复核仍待归档。[原漏检控制](../results/v2/original-misses/known_recovery_summary.json)

## 独立拟合

以公开归档的 v1 盲搜成员作为独立输入，使用 Find_Orb 命令行 2026-10-21 版、JPL DE440 和 W84 站点重新拟合。输入是观测中点 UTC 的匿名 MPC 80 列记录，未附带各测量的拟合误差。Find_Orb 使用全部 23 个 TV158 位置和四个 OF201 位置，报告 RMS 分别为 0.11667″ 和 0.03690″。OF201 的独立拟合在抛物线边界附近（偏心率 1.00214），四点短弧对轨道能量约束弱。脚本、星历与输入记录的散列在仓库中可核验。[Find_Orb](https://www.projectpluto.com/fo_usage.htm) · [TV158 独立拟合](../results/v2/find_orb_v1_tv158.json) · [OF201 独立拟合](../results/v2/find_orb_v1_of201.json)

## 独立试点的冻结范围

采用 Legacy 采样节奏、NSC 曝光覆盖和曝光源密度作初选，冻结中心 RA 38°、Dec +10°，核心半径 0.20°，读取半径 0.96°。时间窗为 MJD 58394.21021082–58407.30271693，含五个 Legacy 夜、10 张曝光、250 个候选 CCD，来自提案 2014B-0404。全部 10 张曝光在 NSC 元数据有唯一匹配。仅排除 DES 提案曝光，天区是否与 DES 搜索重叠需要单独核验。主运行保留 SNR ≥ 5、24 个距离箱。关联内部按种子参考时刻的 SSB 切平面深度分箱；最终轨道另按种子参考时刻的日心瞬时距离 30–300 au 验收。该试点只有一个核心与读取缓冲区，不声明连续多分片覆盖。[选区证据](../results/v2/nsc_pilot_selection.json) · [冻结参数](../configs/v2-nsc-pilot.json)

## 尚待验收

原漏检控制的逐历元复核、试点搜索与置换的完整覆盖、歧义静态分支、两个目标的跨季增长、候选图像与扩展身份检查、分层目录注入，都需要将运行结果和退出状态归档。当前不能从控制场或该试点推断全 DR11 搜索完整度，也未测量图像级完整度。
