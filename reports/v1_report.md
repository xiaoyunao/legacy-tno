# Legacy TNO v1 试点运行报告

状态 **partial**。

DR11 CP 独立提表和匿名关联回收了 **2** 个已知对象，2013 TV158、2017 OF201。同一对象在不同阈值分支的复现按一个对象计数。

独立非 DES 小区在孔径 SNR ≥ 8 的冻结条件下完成全部距离箱，核心覆盖 0.122 平方度，23 个曝光和 10 个独立夜。通过轨道拟合的候选链 0 条。

持久项目位于 /global/homes/y/yunao/projects/legacy-tno，源表和完整观测成员位于 /pscratch/sd/y/yunao/legacy-tno。

[私人 GitHub 仓库](https://github.com/xiaoyunao/legacy-tno) · [跨运行 manifest](../results/v1/run_manifest.json)

## DR11 数据和独立提表

完整 DR11 DECam survey-ccds 和 ccds-annotated 各有 18,171,054 条记录，涵盖 300,004 个曝光号，日期为 2013-08-31 至 2024-09-11 UTC。10,766,364 条通过全部 CCD cuts，另有 4,561,714 条仅触及静态深度选择位。

产品抽查覆盖 14 个跨日期和波段的 S29 CCD 样本，42 份 science、weight 和 DQ 文件均可读。DR9、DR10 和 DR11 的 SExtractor 抽样路径均缺少独立检测表。试点直接从 CP 三件套生成 SEP 独立源表。Gaia EDR3 和 DR11 Sweep 分别用于天测和静态清理。

[全表清点](../results/v1/audit/inventory_summary.json) · [产品审计](../results/v1/audit/catalog_audit.json) · [选区评分](../results/v1/audit/selected-fields.json)

## 试点处理范围

| 区域 | UTC 日期 | 核心覆盖 deg² | 读取并集 deg² | 核心至少四夜 deg² | CCD 成功/计划 | 曝光 | 夜 | 季 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| validation | 2017-11-14 至 2017-11-29 | 1.969 | 2.852 | 1.898 | 670/670 | 11 | 11 | 1 |
| validation-deep | 2014-12-16 至 2015-01-17 | 1.030 | 2.654 | 0.888 | 928/928 | 36 | 12 | 1 |
| validation-bright | 2014-12-16 至 2015-01-17 | 1.030 | 2.654 | 0.888 | 928/928 | 36 | 12 | 1 |
| of201 | 2018-07-25 至 2018-10-31 | 3.717 | 8.631 | 2.430 | 962/962 | 38 | 13 | 1 |
| exploration | 2021-02-20 至 2021-06-02 | 2.455 | 7.364 | 0.060 | 1163/1163 | 63 | 25 | 1 |
| exploration-narrow | 2021-03-01 至 2021-03-24 | 0.122 | 1.477 | 0.077 | 283/283 | 23 | 10 | 1 |

面积来自 CCD 元数据 TAN 足迹并集，以 0.025° 网格积分。四夜面积按固定天区位置计算。探索区按采样选定并排除 DES 提案 2012B-0001，验证区使用 DES 已知对象的几何机会辅助选区。

## 盲关联、测轨和身份

SEP 源表保留积分 SNR ≥ 4.25 的测量。主搜索使用 SNR ≥ 5，结合历元 Gaia、Sweep 同波段点源通量及跨夜持久性清理静态源。关联使用距离箱内的视差和太阳逃逸速度限制两夜位移，第三夜容许区含有界径向速度和曲率余量，随后增长到四个独立夜。匿名轨道拟合采用 DE440s 主要天体摄动、CTIO 测站和迭代光行时。拟合完成后才读取 DES 发布表核对身份。

### validation

运行 validation-c36e0a643fc984，Slurm 61346087，运行代码 e56fee42cb2ffb6440fbac3ac6fcdc3a6a5dfba5，管线记录 field_processed，Slurm 状态 COMPLETED，退出码 0:0。
后验身份核对使用 MJD 57388.5 TDB，代码 d92781a1e259b3c58430ea629b5d3a3b9a606672。
天测校正后的 743,927 条检测中，282,237 条为可靠静态匹配，376,058 条为静态邻近歧义，5,424 条进入主盲搜。
累计检查 496,095 个距离箱内配对和 2,147 个三元组合，生成 0 条链。截断距离箱 0 个。
DES 对象 A（几何）→B（原始检出）→C（清理后）→D（冻结配置可链接）→E（纯净盲回收）为 **2→0→0→0→0**。引导旁支 F 为 **0**。

- 2013 RD124，约 r=22.81，几何曝光 11，原始匹配 0，清洁匹配 0，结论 no_catalog_detection。
- 2013 RQ157，约 r=23.59，几何曝光 9，原始匹配 0，清洁匹配 0，结论 no_catalog_detection。

身份未解决链 0 条，有污染或身份歧义的链 0 条。

Gaia 逐 CCD 散布的中位数为 0.018″（RA cos Dec）和 0.019″（Dec）。权重换算噪声与 SEP 背景 RMS 的中位比值为 1.007。

[结果和 manifest](../results/v1/validation/)
[candidates_and_association](../results/v1/validation/figures/candidates_and_association.png) · [coverage_depth_seasons](../results/v1/validation/figures/coverage_depth_seasons.png)

### validation-deep

运行 validation-97d3348bc5c4b3，Slurm 61346626，运行代码 e56fee4，管线记录 running，Slurm 状态 TIMEOUT，退出码 0:0。
后验身份核对使用 MJD 57388.5 TDB，代码 d92781a1e259b3c58430ea629b5d3a3b9a606672。
天测校正后的 1,612,244 条检测中，229,738 条为可靠静态匹配，1,150,323 条为静态邻近歧义，33,140 条进入主盲搜。
累计检查 14,024,001 个距离箱内配对和 556,437 个三元组合，生成 15 条链。截断距离箱 14 个。
截断分片外的有效面积与轨道机会需要单独估算。下列已知对象计数记录实际证据，回收率分母须避开截断分片。
DES 对象 A（几何）→B（原始检出）→C（清理后）→D（冻结配置可链接）→E（纯净盲回收）为 **2→1→1→1→1**。引导旁支 F 为 **0**。

- 2013 TG228，约 r=24.05，几何曝光 3，原始匹配 0，清洁匹配 0，结论 no_catalog_detection。
- 2013 TV158，约 r=22.07，几何曝光 26，原始匹配 26，清洁匹配 23，结论 blind。

身份未解决链 1 条，有污染或身份歧义的链 0 条。
- **2013 TV158**，23 个一致成员，6 夜，弧长 31.90 天，双分量拟合 RMS 0.107″，整夜留出 RMS 范围 0.043–0.444″。
- C0002，8 个检测、4 夜、26.94 天，RMS 0.209″，名义解 束缚（e=0.988）。

Gaia 逐 CCD 散布的中位数为 0.010″（RA cos Dec）和 0.010″（Dec）。权重换算噪声与 SEP 背景 RMS 的中位比值为 1.005。

[结果和 manifest](../results/v1/validation-deep/)
[candidates_and_association](../results/v1/validation-deep/figures/candidates_and_association.png) · [coverage_depth_seasons](../results/v1/validation-deep/figures/coverage_depth_seasons.png) · [known_residuals_C0001](../results/v1/validation-deep/figures/known_residuals_C0001.png) · [known_track_C0001](../results/v1/validation-deep/figures/known_track_C0001.png)

### validation-bright

运行 validation-c0697ed30f0e61，Slurm 61347410，运行代码 4eda5f87c87147f8f79dfde47ebef19bf4646837，管线记录 partial，Slurm 状态 COMPLETED，退出码 0:0。
天测校正后的 1,612,244 条检测中，229,738 条为可靠静态匹配，1,150,323 条为静态邻近歧义，33,140 条进入主盲搜。
该运行另设关联层孔径 SNR ≥ 8。有效关联输入 28,341 条。
累计检查 13,083,974 个距离箱内配对和 481,991 个三元组合，生成 22 条链。截断距离箱 13 个。
截断分片外的有效面积与轨道机会需要单独估算。下列已知对象计数记录实际证据，回收率分母须避开截断分片。
DES 对象 A（几何）→B（原始检出）→C（清理后）→D（冻结配置可链接）→E（纯净盲回收）为 **2→1→1→1→1**。引导旁支 F 为 **0**。

- 2013 TG228，约 r=24.05，几何曝光 3，原始匹配 0，清洁匹配 0，结论 no_catalog_detection。
- 2013 TV158，约 r=22.07，几何曝光 26，原始匹配 26，清洁匹配 23，结论 blind。

身份未解决链 1 条，有污染或身份歧义的链 0 条。
- **2013 TV158**，23 个一致成员，6 夜，弧长 31.90 天，双分量拟合 RMS 0.107″，整夜留出 RMS 范围 0.043–0.444″。
- C0002，8 个检测、4 夜、26.94 天，RMS 0.209″，名义解 束缚（e=0.988）。

Gaia 逐 CCD 散布的中位数为 0.010″（RA cos Dec）和 0.010″（Dec）。权重换算噪声与 SEP 背景 RMS 的中位比值为 1.005。

[结果和 manifest](../results/v1/validation-bright/)
[candidates_and_association](../results/v1/validation-bright/figures/candidates_and_association.png) · [coverage_depth_seasons](../results/v1/validation-bright/figures/coverage_depth_seasons.png) · [known_residuals_C0001](../results/v1/validation-bright/figures/known_residuals_C0001.png) · [known_track_C0001](../results/v1/validation-bright/figures/known_track_C0001.png)

### of201

运行 validation-7185aa85687161，Slurm 61347163，运行代码 0cd453a2c19ce6dc4035ee2b28eff973e2de8e37，管线记录 partial，Slurm 状态 COMPLETED，退出码 0:0。
天测校正后的 1,143,808 条检测中，568,537 条为可靠静态匹配，371,112 条为静态邻近歧义，20,162 条进入主盲搜。
累计检查 11,805,750 个距离箱内配对和 783,974 个三元组合，生成 333 条链。截断距离箱 13 个。
截断分片外的有效面积与轨道机会需要单独估算。下列已知对象计数记录实际证据，回收率分母须避开截断分片。
DES 对象 A（几何）→B（原始检出）→C（清理后）→D（冻结配置可链接）→E（纯净盲回收）为 **0→0→0→0→0**。引导旁支 F 为 **0**。

独立 Horizons 四夜压力测试目标 2017 OF201，覆盖 4 个曝光及 4 夜，原始检测 4，清洁检测 4，D=1，E=1。

身份未解决链 4 条，有污染或身份歧义的链 0 条。
- C0001，5 个检测、4 夜、81.75 天，RMS 0.201″，名义解 束缚（e=0.990）。
- C0002，4 个检测、4 夜、97.76 天，RMS 0.055″，名义解 非束缚（e=1.437）。
- C0003，4 个检测、4 夜、97.76 天，RMS 0.102″，名义解 束缚（e=0.981）。
- **2017 OF201**，4 个一致成员，4 夜，弧长 96.74 天，双分量拟合 RMS 0.038″。
- C0005，4 个检测、4 夜、81.75 天，RMS 0.076″，名义解 非束缚（e=1.296）。

Gaia 逐 CCD 散布的中位数为 0.013″（RA cos Dec）和 0.024″（Dec）。权重换算噪声与 SEP 背景 RMS 的中位比值为 1.007。

[结果和 manifest](../results/v1/of201/)
[candidates_and_association](../results/v1/of201/figures/candidates_and_association.png) · [coverage_depth_seasons](../results/v1/of201/figures/coverage_depth_seasons.png) · [known_residuals_C0004](../results/v1/of201/figures/known_residuals_C0004.png) · [known_track_C0004](../results/v1/of201/figures/known_track_C0004.png)

### exploration

运行 exploration-f742d8b20d9ab4，Slurm 61347072，运行代码 0cd453a2c19ce6dc4035ee2b28eff973e2de8e37，管线记录 running，Slurm 状态 CANCELLED by submitting user，退出码 0:0。
天测校正后的 1,329,446 条检测中，811,111 条为可靠静态匹配，336,596 条为静态邻近歧义，16,608 条进入主盲搜。
累计检查 14,705,682 个距离箱内配对和 1,342,349 个三元组合，生成 37 条链。截断距离箱 18 个。
截断分片外的有效面积与轨道机会需要单独估算。下列已知对象计数记录实际证据，回收率分母须避开截断分片。
DES 对象 A（几何）→B（原始检出）→C（清理后）→D（冻结配置可链接）→E（纯净盲回收）为 **0→0→0→0→0**。引导旁支 F 为 **0**。


身份未解决链 1 条，有污染或身份歧义的链 0 条。
- C0001，8 个检测、4 夜、67.84 天，RMS 0.243″，名义解 非束缚（e=64.478）。

Gaia 逐 CCD 散布的中位数为 0.014″（RA cos Dec）和 0.016″（Dec）。权重换算噪声与 SEP 背景 RMS 的中位比值为 1.016。

[结果和 manifest](../results/v1/exploration/)
[candidates_and_association](../results/v1/exploration/figures/candidates_and_association.png) · [coverage_depth_seasons](../results/v1/exploration/figures/coverage_depth_seasons.png)

### exploration-narrow

运行 exploration-cb6d398cc191bd，Slurm 61347537，运行代码 d92781a1e259b3c58430ea629b5d3a3b9a606672，管线记录 completed，Slurm 状态 COMPLETED，退出码 0:0。
天测校正后的 275,515 条检测中，64,354 条为可靠静态匹配，171,743 条为静态邻近歧义，3,837 条进入主盲搜。
该运行另设关联层孔径 SNR ≥ 8。有效关联输入 3,055 条。
累计检查 726,082 个距离箱内配对和 5,175 个三元组合，生成 0 条链。截断距离箱 0 个。
DES 对象 A（几何）→B（原始检出）→C（清理后）→D（冻结配置可链接）→E（纯净盲回收）为 **0→0→0→0→0**。引导旁支 F 为 **0**。


身份未解决链 0 条，有污染或身份歧义的链 0 条。

Gaia 逐 CCD 散布的中位数为 0.016″（RA cos Dec）和 0.018″（Dec）。权重换算噪声与 SEP 背景 RMS 的中位比值为 1.026。

[结果和 manifest](../results/v1/exploration-narrow/)
[candidates_and_association](../results/v1/exploration-narrow/figures/candidates_and_association.png) · [coverage_depth_seasons](../results/v1/exploration-narrow/figures/coverage_depth_seasons.png)

## 初始验证区的漏检归因

- 2013 RD124，11 次 Horizons 位置强制测光，SNR 中位数 1.73，峰值 3.23，J2016.0 与 Horizons 相比 RMS 0.027″。
- 2013 RQ157，9 次 Horizons 位置强制测光，SNR 中位数 0.83，峰值 3.11，J2016.0 与 Horizons 相比 RMS 0.031″。

[独立星历和漏点诊断](../results/v1/validation/known_miss_diagnostic.json)

## 验证和计算成本

2013 TV158 匿名短弧的束缚解敏感性实验中，自由拟合的 RMS 为 0.107″，施加太阳逃逸速度约束后的 RMS 为 0.107″，拟合 χ² 增加 0.109。短弧的径向速度和轨道能量仍有退化。

[束缚解敏感性](../results/v1/validation-deep/bound_fit_sensitivity.json)

宽探索区未解决链的整夜留出 RMS 为 0.64–349.49″。CP 邮票显示末夜 z 波段检测邻近明显的横向条纹，中心 DQ 值为 0。该链的身份仍待核，当前证据等级低。

[候选审查](../results/v1/exploration/candidate_review.json)

另以 2017 OF201 的公开 W84 观测作匿名测轨实验。10 个测量跨 9 夜和 1539.8 天，拟合 RMS 0.088″，整夜留出汇总 RMS 0.127″。该实验使用已发表的成员测量。
同历元 W84 Horizons ICRF 星历对照的双分量 RMS 为 0.083″，最大角分离 0.208″。

[拟合验证](../results/v1/audit/anonymous_orbit_benchmark.json) · [公开测量](https://arxiv.org/html/2505.15806v2) · [Horizons](https://ssd-api.jpl.nasa.gov/doc/horizons.html)

- validation 注入组 all_points_present，完整批次回收 **16/16**，另有 0 个对象所在批次触及预算。
- validation 注入组 hypothetical_missingness，完整批次回收 **3/16**，另有 0 个对象所在批次触及预算。
- validation 整夜置换对照为 0 条，0 个截断箱。组内相对时间保持，真实时刻与视差的对应关系被打乱。
- validation 运行 529.3 s，主进程峰值 RSS 12.15 GiB，工作目录 1.13 GiB。
- validation-deep 整夜置换对照为 2 条，14 个截断箱。组内相对时间保持，真实时刻与视差的对应关系被打乱。
- validation-bright 整夜置换对照为 0 条，13 个截断箱。组内相对时间保持，真实时刻与视差的对应关系被打乱。
- validation-bright 运行 165.3 s，主进程峰值 RSS 2.88 GiB，工作目录 1.66 GiB。
- of201 整夜置换对照为 6 条，14 个截断箱。组内相对时间保持，真实时刻与视差的对应关系被打乱。
- of201 运行 354.8 s，主进程峰值 RSS 11.82 GiB，工作目录 1.19 GiB。
- exploration 整夜置换对照为 0 条，18 个截断箱。组内相对时间保持，真实时刻与视差的对应关系被打乱。
- exploration-narrow 注入组 all_points_present，完整批次回收 **2/8**，另有 0 个对象所在批次触及预算。
- exploration-narrow 注入组 hypothetical_missingness，完整批次回收 **0/8**，另有 0 个对象所在批次触及预算。
- exploration-narrow 整夜置换对照为 0 条，0 个截断箱。组内相对时间保持，真实时刻与视差的对应关系被打乱。
- exploration-narrow 运行 225.0 s，主进程峰值 RSS 10.91 GiB，工作目录 0.42 GiB。

注入两组分别指定进入源表的点和假定的噪声、缺测。像素提取、混叠和图像级完整性需要专门实验。

Slurm 退出和资源用量见 [记账记录](../logs/slurm-accounting.psv)。初次试点触及压缩 annotated FITS 和选区的内存上限。后续作业采用磁盘暂存和紧凑选区字段。

## 边界和验收

30–300 au 为工程距离范围。两区的固定时间窗、天空边界、质量掩膜和实际采样共同决定覆盖。短弧轨道和局部协方差可能严重退化。身份核对覆盖 DES 验证目录。完整 MPC 比对、跨季增长、歧义静态全分支、像素级确认和扩大注入仍是验收缺项。四夜 OF201 压力测试采用 4 个检测的门槛，原始六检测门槛保留在其他主支。OF201 每次留出一夜后只余 3 个测量，留出预测保持缺失状态。2013 TV158 的留出优化使用原匿名链的初始状态。宽区域的截断、超时和提前结束的注入均列在记账和 manifest 中。

复跑入口见 [运行手册](../docs/operations.md)，其他范围限制见 [限制记录](../docs/limitations.md)。
