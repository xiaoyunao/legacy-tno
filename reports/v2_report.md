# Legacy TNO v2 实测运行报告

本版以 DR11 DECam 的物理曝光为母样本，复用 NOIRLab NSC DR2 的逐 CCD 独立检测。真实源表、每个 CCD 的可用性明细、盲搜成员 ID 和完整中间数据保存在 NERSC scratch。本报告记录已核实的运行结果，并标明尚未验收的范围。

## 数据入口

在 NERSC 的 DR11 data 和 work 根目录核验五个归档场及独立试点共 7,946 条唯一 SE 路径，其中归档场 7,446 条。作业 61393062 直接用 DR11.1.0 上游的命名方法在真实 CCD 元数据上重建 `im.sefn`，逐条和当时的路径审计核对一致。这些路径在本次检查中均缺失。上游流水线可以生成 SE 文件，并会在合并 PSFEx 产品通过校验后清理逐 CCD 文件。具体曝光是否曾生成以及其他区域是否公开保留，超出本次路径核验范围。[SE 审计](../results/v2/legacy_se_fields_summary.json) · [逐路径上游复核](../results/v2/legacy_se_upstream_verified.json) · [上游清理逻辑](https://github.com/legacysurvey/legacypipe/blob/769e266b837196a7d5c2dfda245cd1f5d64abd91/py/legacyzpts/legacy_zeropoints.py#L355-L372)

通过 NOIRLab Query Client 读取 `nsc_dr2.exposure`、`chip`、`meas`，按 DECam EXPNUM、UTC 曝光起始时刻、波段、曝光时长和 CP 图像 HDU 上的物理 CCD 编号核对。三组归档控制场的 Legacy 曝光与 NSC 匹配分别为 11/11、35/36、38/38。共同 CCD 分别为 670/670、923/928、962/962。归档的两个 2021 年窗口没有 NSC DR2 曝光匹配。该年份缺口保留 SEP 路径和原有实测结果。[曝光审计](../results/v2/nsc_inventory_summary.json) · [CCD 审计](../results/v2/nsc_ccd_summary.json) · [NSC DR2 测量定义](https://datalab.noirlab.edu/data-explorer?showTable=nsc_dr2.meas)

| 控制场 | 实读 NSC 源 | 归一化后保留 | Slurm 归一化 |
|---|---:|---:|---|
| 2013 TV158 | 1,356,317 | 1,351,521 | 61392190，167 s，0:0 |
| 2017 OF201 | 936,200 | 931,799 | 61392191，173 s，0:0 |
| 2013 RD124 / 2013 RQ157 | 621,504 | 619,380 | 61392310，108 s，0:0 |

每组测量返回行数均和 NSC 芯片索引一致。下载以曝光与一至八个 CCD 组为单位缓存，保留测量 ID。适配器采用 CP 的 UTC 起始时刻加半曝光时长，将 NSC 的 AUTO AB 星等转换为纳米马吉，使用 RA、Dec 两个角秒位置误差中较大的值作为共同权重分量。CP 权重、DQ、边缘和 NSC 提源旗标提供质量筛选。按曝光历元传播 Gaia 星表，实测 CCD 偏移与散布。NSC 原有标定位置进入拟合，附加散布下限 0.15″。NSC AUTO 流量和 Sweep PSF 流量的显著超量判定在本版关闭。默认关联输入仅含通过静态与质量筛选且 SNR ≥ 5 的检测，静态歧义检测仍留在分类结果。

三个控制场和独立试点共 2,810 个 Legacy CCD，其中 2,805 个可直接使用 NSC，覆盖 94/95 张曝光。唯一缺口出现在 TV158 场的一张曝光。2021 年宽、窄归档场的 1,163 和 283 个 CCD 均无 NSC 曝光匹配，现有 SEP 归档支持两个范围。这两个视场可能重叠。逐 CCD 账本合并了 Legacy 路径、NSC 查询键、实际载入与 Gaia 校验状态、检测数和足迹索引，保存在 NERSC 的 `v2/nsc-coverage-ledger.json`。[按场、年份和波段的覆盖表](../results/v2/nsc-coverage-public.json) · [覆盖与年份图](../results/v2/figures/nsc_coverage.png)

独立后备分支在缺少 NSC 的 EXPNUM 389798 上运行 SEP。五个 CCD 全部通过 Gaia 检查，共提取 5,477 个测量，重复读取均命中 SEP 缓存。关闭后备时，这五个 CCD 保持缺失，NSC-only 的回收统计据此计数。该测试只计作后备产品可用性。[SEP 后备分支实测](../results/v2/nsc-sep-fallback.json)

两控制场中选取包含已回收成员的 27 个共同 CCD，NSC 和 SEP 分别有 36,085 和 43,571 条源记录，获得 33,585 个 1″ 内的互为最近邻配对。按波段和 SEP 星等分组报告位置差与 AUTO − 孔径星等的分位数。各星等组的匹配位置偏差中位数约为 0.016–0.089″；AUTO 与 SEP 孔径差有波段及亮度依赖，无法用单一零点平移概括。各场各波段的 Gaia 东、北分量 CCD 中位偏移绝对值均小于 0.036″。归一化没有强制将 Gaia 偏移写回 NSC 坐标。[同 CCD 统计](../results/v2/nsc-sep-by-magnitude.json) · [星等趋势图](../results/v2/figures/nsc_sep_comparison.png) · [Gaia 与 CP 掩膜质控](../results/v2/nsc-qc-summary.json)

同一批 CCD 内，按波段将 CCD 物理像素位置划为 4×4 网格，各格中位位置分离为 0.033–0.089″，统计覆盖全部 33,585 个配对。进入静态分类的 SEP 和 NSC 分别有 43,571 和 35,950 条，其中干净瞬变分类有 876 和 211 条，定义及分类标志见逐 CCD 统计。两套提源和测光的差异也会改变输入池构成。

在上游 NSC 的 DR2 自行修正实现中，`raerr` 由角秒转为毫角秒，权重对应已乘以 cos δ 的东西向位置差。这里直接使用角秒误差，不再重复乘 cos δ。拟合残差由单位方向投影至局部东西和南北基底。[NSC 上游切平面换算](https://github.com/noaodatalab/noaosourcecatalog/blob/7c0756eea30b7a3afcab0e204310ee39e1c5dabc/python/nsc/fix_pms.py#L229-L240)

## 冻结全池盲搜

| 目标 | A 几何曝光 | B 实测 | C 入池 | D 可关联 | E 盲搜 | 相应距离箱 |
|---|---:|---:|---:|---|---|---|
| 2013 TV158 | 26 | 23 | 23 | 是 | 23 个纯成员，六夜 | 24/24 完成 |
| 2013 TG228 | 3 | 0 | 0 | 否 | 无 | 与 TV158 同一场 |
| 2017 OF201 | 4 | 3 | 3 | 否 | 无 | 9/24 完成 |
| 2013 RD124 | 11 | 0 | 0 | 否 | 无 | 24/24 完成 |
| 2013 RQ157 | 9 | 0 | 0 | 否 | 无 | 与 RD124 同一场 |

表中 A–F 取自盲搜后目标核对。五个控制对象均无仅引导拟合成功（F）。表中的 TG228 A 采用 DES 状态和 TAN 足迹判据，独立 Horizons 加 CP WCS 得到四个 CCD 位置，其中两处没有可用的中心像素或产品，两处未在 1.25″ 内检出。TV158 场 923/928 个 CCD 有 NSC 产品，限制来自同一曝光中缺失的五片 CCD。3,861 个干净检测参加匿名关联。单条纯成员链的拟合弧长 31.90 天，东西与南北残差的合并 RMS 为 0.0445″。留出六个整夜时每次由训练位置重新初始化，RMS 为 0.0485–0.0741″。整夜重排通过拟合的链数为 0，无距离箱截断。[TV158 运行记录](../results/v2/tv158/run_manifest.json) · [候选摘要](../results/v2/tv158/candidate_summary.json) · [独立历元审计](../results/v2/nsc-horizons-tv158.json)

OF201 场用于测试四夜门槛。共 23,810 个干净检测进入搜索。真实场七条四夜链通过数值拟合，夜重排六条，分别有 15、16 个距离箱触发上限。OF201 第四个预期历元为 EXPNUM 759212、N26、z 波段。独立 Horizons W84 星历位置上 CP 中心 DQ 为 0，9×9 像素窗可用比例为 98.8%，最近 NSC 源在 32.66″ 外。同 CCD SEP 对照找到了该历元的 v1 检测。盲搜本体写齐结果后，作业 61392252 的 Slurm 文件名解析以 2:0 退出，独立身份后处理由作业 61392263 完成（24 s，0:0）。[OF201 盲搜范围](../results/v2/of201/search_domain_summary.json) · [回收结果](../results/v2/of201/stress_recovery_summary.json) · [独立历元审计](../results/v2/nsc-horizons-of201.json)

原漏检控制场作业 61392388 完成（280 s，0:0）。5,289 个干净检测参加盲搜，主搜索和夜重排均无截断或通过拟合的链。独立 Horizons 和实际 CP WCS 复核到 11 个 RD124 及 9 个 RQ157 覆盖位置，中心可用且均无 1.25″ 内的 NSC 检测。[原漏检控制](../results/v2/original-misses/known_recovery_summary.json) · [独立历元审计](../results/v2/nsc-horizons-original-misses.json)

## 独立拟合

以公开归档的 v1 盲搜成员作为独立输入，使用 Find_Orb 命令行 2026-10-21 版、JPL DE440 和 W84 站点重新拟合。输入是观测中点 UTC 的匿名 MPC 80 列记录，未附带各测量的拟合误差。Find_Orb 使用全部 23 个 TV158 位置和四个 OF201 位置，报告 RMS 分别为 0.11667″ 和 0.03690″。OF201 的独立拟合在抛物线边界附近（偏心率 1.00214），四点短弧对轨道能量约束弱。脚本、星历与输入记录的散列在仓库中可核验。[Find_Orb](https://www.projectpluto.com/fo_usage.htm) · [TV158 独立拟合](../results/v2/find_orb_v1_tv158.json) · [OF201 独立拟合](../results/v2/find_orb_v1_of201.json)

## 已知库与候选图像审查

对匿名链逐历元查询 2026-11-16 UTC 冻结的 MPCORB 小行星轨道快照（1,580,903 条），使用 Astcheck 在 W84 站点、120″ 半径和预测可见星等 30 的界限下作多夜初筛。TV158 链只得到一个多夜关联，MPC 编码 h7360 覆盖全部六夜，JPL 编号 437360 对应 2013 TV158。初筛坐标的分量 RMS 为 42.34″，身份判断结合独立 Horizons 复核。OF201 场七条四夜链均无多夜 MPCORB 初筛匹配，单历元均未达到返回限制。[JPL SBDB 记录](https://ssd-api.jpl.nasa.gov/sbdb.api?sstr=437360) · [TV158 MPCORB 筛查](../results/v2/tv158/mpcorb_review.json) · [OF201 场 MPCORB 筛查](../results/v2/of201/mpcorb_review.json)

作业 61392580 生成了七条 OF201 场匿名链的全部 28 个逐夜 CP 图像、DQ 和权重小图。各检测中心 DQ 为 0。目视仍发现拉长特征、亮源混叠和条带，四夜轨道在仅用三夜初始化时只有 6/28 次获得可用预测。七条链的证据不足以列为优先天体候选。图中青圈标记检测位置，橙色十字标记轨道预测。[图像与留出记录](../results/v2/of201/candidate_review.json) · [OF201 的 v1 SEP 对照小图](../results/v2/of201-sep/figures/candidate_stamps_C0004.png)

逐检测成员比对证实 C0002 与 C0003 共享三夜，C0004 与 C0007 共享两夜。需将它们视为竞争关联。原始候选编号保留供追溯。[成员交集与距离箱计时](../results/v2/nsc-link-bin-profiles.json) · [七条候选轨迹](../results/v2/of201/figures/candidate_tracks.png)

| 匿名链 | 训练夜独立预测 | 图像审查 |
|---|---:|---|
| [C0001](../results/v2/of201/figures/candidate_stamps_C0001.png) | 1/4 | 首夜检测沿细条纹，后续两夜有混叠，组合伪迹 |
| [C0002](../results/v2/of201/figures/candidate_stamps_C0002.png) | 2/4 | 末夜弯曲细线，首夜受邻近亮源影响，组合伪迹 |
| [C0003](../results/v2/of201/figures/candidate_stamps_C0003.png) | 2/4 | 前三夜图像与 C0002 一致，末夜选择同类弯曲细线，竞争关联且有伪迹 |
| [C0004](../results/v2/of201/figures/candidate_stamps_C0004.png) | 1/4 | 首夜弯曲条纹，第二夜模型与检测位置分离，组合伪迹 |
| [C0005](../results/v2/of201/figures/candidate_stamps_C0005.png) | 0/4 | 首夜长条通过检测中心，第二夜有大范围亮源混叠，组合伪迹 |
| [C0006](../results/v2/of201/figures/candidate_stamps_C0006.png) | 0/4 | 第二夜受邻源混叠且模型偏离；身份未识别、低可信 |
| [C0007](../results/v2/of201/figures/candidate_stamps_C0007.png) | 0/4 | 中间两夜与 C0004 图像一致，末夜检测沿长条纹，竞争关联且有伪迹 |

## 跨季增长

OF201 从 v1 盲搜得到的四个 SEP 成员初始化 23 个短弧可接受轨道，搜索至短弧端点前后 760 天内的 Legacy 曝光。三处预测落入实际 CCD，三者均能读取 NSC 星表。两个 NSC 检测分别来自 EXPNUM 661358/S22 和 678449/S28。用其中一夜重拟合后，对另一夜的双向独立预测偏差为 0.37″ 和 0.85″；两处随后均由 Horizons W84 确认为同一目标。开放两夜后的六点拟合分量 RMS 为 0.0794″，弧长由 96.74 天扩至 464.73 天。新增测量均来自原 Legacy 母样本的独立 NSC 检测，本次增长未使用强制测光。[OF201 跨季评分](../results/v2/nsc-grow-of201-scored.json)

TV158 从 v2 的 23 个匿名 NSC 成员初始化 28 个轨道，检查 111 个跨季 CCD 机会，其中 98 个可读 NSC，13 个没有可唯一匹配的 NSC 曝光。从 145 个测量候选构建 336 个去重双夜配对，试验 24 个匿名种子，迭代选择每次曝光最多一个成员。最佳链的 20 个附加测量覆盖七夜，全部通过独立 Horizons 的 1.25″ 判据。联合拟合使用 43 个测量，弧长从 31.90 天扩至 444.89 天，分量 RMS 为 0.0623″。七个新增夜的独立留出角距离 RMS 为 0.035–0.202″。新增测量同样全部来自 Legacy 曝光的独立 NSC 星表。[TV158 联合拟合及评分](../results/v2/nsc-grow-tv158-refined-summary.json)

| 目标 | 初始／联合拟合测量数 | 距离局部 σ（au） | 1/a 局部 σ（au⁻¹） |
|---|---:|---:|---:|
| 2013 TV158 | 23 → 43 | 0.0203 → 0.00352 | 1.85×10⁻³ → 5.26×10⁻⁵ |
| 2017 OF201 | 4 → 6 | 0.115 → 0.00668 | 1.48×10⁻² → 9.66×10⁻⁴ |

这些误差从指定单点误差和局部线性化雅可比获得。OF201 联合解的 1/a 为 0.00130 au⁻¹，与其局部误差同量级，轨道能量仍弱约束。两个已知目标的逐源文件与所有竞争轨道保存在 NERSC，公开表仅含匿名选择摘要和最终评分。[OF201 联合拟合](../results/v2/nsc-grow-of201-refined-summary.json) · [弧长与局部约束图](../results/v2/figures/nsc_growth.png)

## 独立试点的冻结范围

采用 Legacy 采样节奏、NSC 曝光覆盖和曝光源密度作初选，冻结中心 RA 38°、Dec +10°，核心半径 0.20°，读取半径 0.96°。时间窗为 MJD 58394.21021082–58407.30271693，含五个 Legacy 夜、10 张曝光、250 个候选 CCD，来自提案 2014B-0404。全部 10 张曝光在 NSC 元数据有唯一匹配。仅排除 DES 提案曝光，天区是否与 DES 搜索重叠需要单独核验。主运行保留 SNR ≥ 5、24 个距离箱。关联内部按种子参考时刻的 SSB 切平面深度分箱；最终轨道另按种子参考时刻的日心瞬时距离 30–300 au 验收。该试点只有一个核心与读取缓冲区，不声明连续多分片覆盖。[选区证据](../results/v2/nsc_pilot_selection.json) · [冻结参数](../configs/v2-nsc-pilot.json)

主搜索作业 61392409 完成（565 s，0:0）。250/250 个 CCD 通过入池核验，覆盖 10 张曝光、五夜。0.025° 网格估计读取覆盖 3.635 deg²，核心有覆盖 0.112 deg²，核心至少四夜覆盖 0.0450 deg²。227,331 条标定记录中有 7,705 条进入主关联，检查 1,060,727 个曝光对组合和 684 个三元组。24 个距离箱全部结束。未形成达到拟合门槛的链，夜重排也无候选或截断。本次结果适用于冻结的天区、时间窗、SNR 门槛和干净源策略。[搜索范围](../results/v2/pilot/search_domain_summary.json) · [覆盖图](../results/v2/pilot/figures/coverage_nights.png) · [夜重排](../results/v2/pilot/null_test_summary.json) · [作业记账](../logs/slurm-v2-accounting.psv)

| 试点分支 | 入池记录 | 关联和拟合用时 | 实场触顶箱 | 夜重排触顶箱 | 实场通过拟合 |
|---|---:|---:|---:|---:|---:|
| SNR ≥ 5 干净源 | 7,705 | 2.35 s | 0/24 | 0/24 | 0 |
| [SNR ≥ 8 独立对照](../results/v2/sensitivity/bright/run_manifest.json) | 6,912 | 1.91 s | 0/24 | 0/24 | 0 |
| [全静态歧义对照](../results/v2/sensitivity/ambiguity/run_manifest.json) | 173,839 | 21.66 s | 21/24 | 18/24 | 0（部分搜索） |

全静态歧义分支额外加入 166,134 条记录，所计关联和拟合用时约为主分支 9.2 倍，已枚举约 4,962 万个点对。该分支出现截断，新增回收数的比较仍受未处理距离箱限制。

进一步把第一种子端点限制在同一试点中心的 0.06° 内。两组共用原读取缓冲区，干净源与包含歧义源两组均完整跑完 24 箱，夜重排同样未截断。干净源关联 0.27 s，零链。含歧义源关联与拟合共 10.97 s，新增一条六点四夜链，夜重排零链。这条链的无约束拟合偏心率为 102.45，四次留夜均无可接受的训练轨道，图像显示多个成员与延展或混叠源重合。MPCORB 无多夜匹配，链判为不可靠。独立小核心的歧义增量因此为一条数值候选、零条审查后天体候选。[有界干净对照](../results/v2/sensitivity/clean-core/run_manifest.json) · [有界歧义对照](../results/v2/sensitivity/ambiguity-core/run_manifest.json) · [新增链图像](../results/v2/sensitivity/ambiguity-core/figures/candidate_stamps_C0001.png) · [留夜与图像记录](../results/v2/sensitivity/ambiguity-core/candidate_review.json)

OF201 应力场用 0.35° 第一端点复跑，将实场截断由 15 箱降到七箱。七条数值链中六条与原场成员完全一致。新增 C0007 首末夜检测沿明显非点源条纹，唯一可行的留夜预测偏差分量 RMS 约为 9.0″，MPCORB 无多夜匹配，判为伪关联。[OF201 有界复跑](../results/v2/sensitivity/of201-core/run_manifest.json) · [成员去重](../results/v2/sensitivity/of201-core/candidate_delta.json) · [新增链图像](../results/v2/sensitivity/of201-core/figures/candidate_stamps_C0007.png)

作业 61392818 重放了冻结的试点与 OF201 场搜索，候选成员、计数、重排映射和距离箱截断均与原运行一致。试点实场关联 2.28 s，没有进入拟合的链，夜重排 1.66 s。OF201 场实场关联 82.87 s、候选拟合 50.62 s、夜重排 202.32 s。试点原运行的星表载入与筛选共 412.75 s，是本场的主要支出。OF201 与全歧义分支扩大后，关联组合数成为限制。[逐箱计时与状态图](../results/v2/figures/nsc_bin_costs.png)

可在 Perlmutter 用冻结代码重跑主试点。作业对已经封存的 NSC 产品使用续跑路径。

```bash
work=/pscratch/sd/y/yunao/legacy-tno
revision=c7cd9e0f4c603a6dcea68cb4b9eb18baab15e345
code="$HOME/projects/legacy-tno/revisions/$revision"
sbatch --account=desi --constraint=cpu --qos=debug \
  -o "$work/v2/nsc-pilot-%j.log" "$code/slurm/v2-nsc-pilot.sbatch" \
  "$code" "$work" "$revision"
```

### 分层目录注入

作业 61392486 完成（138 s，0:0）。使用同一组真实曝光时刻、CCD 足迹与背景星表，将 12 条独立开普勒轨迹分六批加入，每批最多两条。按三个距离层和两个星等层各注入两条，每条轨迹满足六次几何曝光。72 条注入测量中 70 条通过静态和质量筛选。纯链回收 4/12，按距离层分别为 30–60 au 的 3/4、60–120 au 的 1/4、120–300 au 的 0/4，六批均未截断。该比例以**已具备可用 CCD 星表且满足几何门槛**为条件。注入包含位置扰动及实测星表的 SNR 近邻估计，对缺乏近邻的测量使用工程估计。每组只有两条轨迹，数据不足以拟合普适回收曲线。图像提源完整度未经注入标定。[逐轨迹统计](../results/v2/pilot/injection_recovery_summary.json) · [各层筛选和回收](../results/v2/pilot/figures/catalog_injection.png)

## 尚待验收

OF201 的 0.16° 复跑仍需归档。该试点的全 DR11 代表性及图像级完整度未经标定。

各阶段的可恢复入口、归档路径和版本用法见 [v2 复跑与续跑](../docs/v2_operations.md)。
