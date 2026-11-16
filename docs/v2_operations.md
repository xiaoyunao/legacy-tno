# Legacy TNO v2 复跑与续跑

在本地仓库运行 `scripts/stage-revision.sh yunao@perlmutter.nersc.gov <git-revision>`，
将该提交中的程序、配置和 Slurm 脚本放入 Perlmutter 的个人版本目录。原始 CP、
Gaia 和 Sweep 产品按只读路径访问，完整 CCD 审计、NSC 查询缓存和逐源文件留在
`/pscratch/sd/y/yunao/legacy-tno`。登录节点用于准备命令和查看账本，计算通过 Slurm 提交。

以下命令在 Perlmutter 执行。

```bash
work=/pscratch/sd/y/yunao/legacy-tno
revisions="$HOME/projects/legacy-tno/revisions"
srun_flags=(--account=desi --constraint=cpu --qos=debug)
```

## 冻结主试点

主试点同时执行 Legacy 元数据选择、指定路径的 SE 审计、NSC 曝光与 CCD 匹配、
按 CCD 取源、标定检查、冻结全池搜索和夜重排。封存的 `v2/prepared-pilot/manifest.json`
存在时，脚本直接从该版本校验过的 CCD 产品续跑。查询缓存按语句散列存放在
`v2/nsc_query_cache`。

```bash
rev=c7cd9e0f4c603a6dcea68cb4b9eb18baab15e345
code="$revisions/$rev"
sbatch "${srun_flags[@]}" -o "$work/v2/nsc-pilot-%j.log" \
  "$code/slurm/v2-nsc-pilot.sbatch" "$code" "$work" "$rev"
```

已归档主试点编号为 `exploration-b49f1211213970`。原漏检控制区、TV158 场及
OF201 场各自的候选输入、标定阈值、场边界和版本保存在相应 `run_manifest.json`。
查看 `logs/slurm-v2-accounting.psv` 的退出状态，再看各运行的 `truncated` 与
`fit_counts`，两者分别约束计算执行和科学分片完成度。

## 复核归档的关联与质控

作业 61392818 使用归档的 `classified.npz` 对主试点和 OF201 应力场复跑，
逐项核对匿名成员、距离箱计数、截断和夜重排映射。它无需重新查询这些 CCD。
`v2-nsc-compare.sbatch` 另核验固定版本上游 `im.sefn`，并复用同曝光 SEP 星表
产出星等、CCD 位置和筛选分类统计。

```bash
rev=ba5ba96548634c55115990fd338ae0ec98f2eba0
code="$revisions/$rev"
sbatch "${srun_flags[@]}" -o "$work/v2/nsc-diagnostics-%j.log" \
  "$code/slurm/v2-nsc-diagnostics.sbatch" "$code" "$work" "$rev"
```

有界分支共用原读取缓冲区和标定星表，并收紧第一种子端点，入口为
`slurm/v2-nsc-core-replay.sbatch`。SNR ≥ 8、全静态歧义和注入是单独的工作流。
`slurm/v2-nsc-pilot-controls.sbatch` 最后一个参数分别取 `bright`、`ambiguity`
或 `injection`，倒数第二个参数为上述已归档主试点目录。

## 匿名跨季拟合与事后评分

`scripts/extend-nsc-season.py` 的输入只有运行和匿名候选编号。输出到
`v2/nsc-grow-*-scored-detail.json` 后，可复用其中的匿名短弧轨道族、备选测量及
双夜预测，直接运行联合拟合与事后 Horizons 评分。

```bash
rev=532db16c6f864d163b4653de7720bbfec71f1071
code="$revisions/$rev"
sbatch "${srun_flags[@]}" -o "$work/v2/nsc-growth-refine-%j.log" \
  "$code/slurm/v2-nsc-growth-refine.sbatch" "$code" "$work"
```

`*-refined-private.json` 中含逐源匿名成员。同步到本地的是
`*-refined-summary.json` 中的评分、约束和留夜统计。保留原候选编号，并单独存储
匿名扩展选择，便于审计目标星历的使用阶段。

## 结果位置

- 每次运行的准确路径通过相应 Slurm 日志中的 `RUN_PATH=` 获取。
- Perlmutter 的 `v2/nsc-coverage-ledger.json` 将物理 CCD、匹配状态、可用性、
  路径和标定状态串在一起。候选逐源成员由各运行的 `blind_candidates.json`
  与 `classified.npz` 对应。
- 本地使用 `.venv/bin/python scripts/plot-v2-diagnostics.py results/v2`
  从归档结果重画覆盖、同 CCD 对照、每箱成本和跨季约束图。
- [v2 实测报告](../reports/v2_report.md) 链接到各份公开结果和运行限制。
