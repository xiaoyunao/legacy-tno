#!/usr/bin/env python3
"""Generate the Chinese report from the reviewed small pilot outputs."""
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT/"results"/"v1"


def get(field, filename):
    path = RESULTS/field/(filename+".json")
    return json.loads(path.read_text()) if path.exists() else None


def day(mjd):
    return (date(1858,11,17) + timedelta(days=mjd)).isoformat()


def report():
    lines=["# Legacy TNO v1 试点运行报告","","状态 **partial**。",""]
    inventory=get("audit","inventory_summary")
    products=get("audit","catalog_audit")
    if inventory and products:
        readable=sum(p["status"]=="readable" for r in products["product_samples"] for p in r["products"])
        lines.extend(["## DR11 数据和独立提表","",
         f"完整 DR11 DECam survey-ccds 和 ccds-annotated 各有 {inventory['survey_rows']:,} 条记录，涵盖 {inventory['distinct_expnum']:,} 个曝光号，日期为 {day(inventory['min_mjd'])} 至 {day(inventory['max_mjd'])} UTC。{inventory['total_passes']:,} 条通过全部 CCD cuts，另有 {inventory['total_depth_only']:,} 条仅触及静态深度选择位。",
         "",
         f"产品抽查覆盖 {len(products['product_samples'])} 个跨日期和波段的 S29 CCD 样本，{readable} 份 science、weight 和 DQ 文件均可读。DR9、DR10 和 DR11 的 SExtractor 抽样路径均缺少独立检测表。试点直接从 CP 三件套生成 SEP 独立源表。Gaia EDR3 和 DR11 Sweep 分别用于天测和静态清理。",
         "",
         "[全表清点](../results/v1/audit/inventory_summary.json) · [产品审计](../results/v1/audit/catalog_audit.json) · [选区评分](../results/v1/audit/selected-fields.json)",""])
    lines += ["## 试点处理范围","",
              "| 区域 | UTC 日期 | 核心覆盖 deg² | 读取并集 deg² | 核心至少四夜 deg² | CCD 成功/计划 | 曝光 | 夜 |",
              "|---|---|---:|---:|---:|---:|---:|---:|"]
    for fid in ("validation","exploration"):
        e=get(fid,"exposure_summary")
        if e:
            lines.append(f"| {fid} | {day(e['mjd_min'])} 至 {day(e['mjd_max'])} | "
                         f"{e['core_covered_deg2']:.3f} | {e['read_area_deg2']:.3f} | {e['core_four_nights_deg2']:.3f} | "
                         f"{e['n_ccd_read']}/{e['n_ccd_requested']} | {e['n_exp']} | {e['nights']} |")
        else:
            lines.append(f"| {fid} | 缺阶段统计 | — | — | — | — | — | — |")
    lines.extend(["","面积来自 CCD 元数据 TAN 足迹并集，以 0.025° 网格积分。四夜面积按固定天区位置计算。探索区按采样选定并排除 DES 提案 2012B-0001，验证区使用 DES 已知对象的几何机会辅助选区。","",
                  "## 盲关联、测轨和身份","",
                  "SEP 源表保留积分 SNR ≥ 4.25 的测量。主搜索使用 SNR ≥ 5，结合历元 Gaia、Sweep 同波段点源通量及跨夜持久性清理静态源。关联使用距离箱内的视差和太阳逃逸速度限制两夜位移，第三夜容许区含有界径向速度和曲率余量，随后增长到四个独立夜。匿名轨道拟合采用 DE440s 主要天体摄动、CTIO 测站和迭代光行时。拟合完成后才读取 DES 发布表核对身份。",""])
    for fid in ("validation","exploration"):
        lines += [f"### {fid}",""]
        manifest=get(fid,"run_manifest")
        if manifest:
            lines.append(f"运行 {manifest['run_id']}，Slurm {manifest.get('slurm_job')}，代码 {manifest['run_code_commit']}，运行状态 {manifest['status']}。")
            if manifest.get("failure"):
                failure=manifest["failure"]
                lines.append(f"失败阶段 {failure['stage']}，错误为 {failure['type']}。")
        static=get(fid,"static_filter_summary")
        if static:
            lines.append(f"天测校正后的 {sum(static.values()):,} 条检测中，{static.get('static_confident',0):,} 条为可靠静态匹配，{static.get('ambiguous_static_match',0):,} 条为静态邻近歧义，{static.get('transient_clean',0):,} 条进入主盲搜。")
        domain=get(fid,"search_domain_summary")
        if domain:
            counts=domain["pair_counts"]
            lines.append(f"累计检查 {counts.get('pairs',0):,} 个距离箱内配对和 {counts.get('triplets',0):,} 个三元组合，生成 {counts.get('chains',0):,} 条链。截断距离箱 {len(domain['truncated'])} 个。")
        truth=get(fid,"known_recovery_summary")
        if truth:
            k=truth["counts"]
            lines.append(f"DES 对象 A（几何）→B（原始检出）→C（清理后）→D（冻结配置可链接）→E（纯净盲回收）为 **{k['A']}→{k['B']}→{k['C']}→{k['D']}→{k['E']}**。引导旁支 F 为 **{k['F_guided_only']}**。")
            lines.append("")
            for r in truth["objects"]:
                lines.append(f"- {r['target']}，约 r={r['m_r']:.2f}，几何曝光 {r['A_geometry_exposures']}，原始匹配 {r['B_raw_detections']}，清洁匹配 {r['C_clean_detections']}，结论 {r['outcome']}。")
        candidates=get(fid,"candidate_summary")
        if candidates is not None:
            counts=Counter(c["status"] for c in candidates)
            lines += ["",f"身份未解决链 {counts['known_status_unresolved']} 条，有污染或身份歧义的链 {counts['contaminated_or_ambiguous']} 条。"]
            for c in candidates:
                if c["status"] == "known_recovered_blind":
                    holds=[h["rms_arcsec"] for h in c.get("held_nights",[]) if "rms_arcsec" in h]
                    hold=f"，整夜留出 RMS 范围 {min(holds):.3f}–{max(holds):.3f}″" if holds else ""
                    lines.append(f"- **{c['catalog_association']}**，{c['n_det']} 个一致成员，{c['n_night']} 夜，弧长 {c['arc_days']:.2f} 天，双分量拟合 RMS {c['rms_arcsec']:.3f}″{hold}。")
        if manifest:
            lines += ["",f"[结果和 manifest](../results/v1/{fid}/)"]
        images=sorted((RESULTS/fid/"figures").glob("*.png"))
        keys=[p for p in images if p.stem.startswith(("known_track","known_residuals","coverage_depth","candidates_and"))]
        if images:
            lines += [" · ".join(f"[{p.stem}](../results/v1/{fid}/figures/{p.name})" for p in keys or images[:3])]
        lines.append("")
    lines += ["## 验证和计算成本",""]
    benchmark=get("audit","anonymous_orbit_benchmark")
    if benchmark:
        lines.append(f"另以 2017 OF201 的公开 W84 观测作匿名测轨实验。{benchmark['n_observations']} 个测量跨 {benchmark['n_nights']} 夜和 {benchmark['n_days']:.1f} 天，拟合 RMS {benchmark['rms_arcsec']:.3f}″，整夜留出汇总 RMS {benchmark['rms_arcsec_held_night']:.3f}″。该实验使用已发表的成员测量。")
        if benchmark.get("horizons"):
            h=benchmark["horizons"]
            lines.append(f"同历元 W84 Horizons ICRF 星历对照的双分量 RMS 为 {h['rms_arcsec']:.3f}″，最大角分离 {h['max_separation_arcsec']:.3f}″。")
        lines += ["","[拟合验证](../results/v1/audit/anonymous_orbit_benchmark.json) · [公开测量](https://arxiv.org/html/2505.15806v2) · [Horizons](https://ssd-api.jpl.nasa.gov/doc/horizons.html)",""]
    for fid in ("validation","exploration"):
        injection=get(fid,"injection_recovery_summary")
        if injection:
            for group in sorted({a["group"] for a in injection["objects"]}):
                complete=[a for a in injection["objects"] if a["group"]==group and not a["search_truncated"]]
                partial=sum(a["group"]==group and a["search_truncated"] for a in injection["objects"])
                lines.append(f"- {fid} 注入组 {group}，完整批次回收 **{sum(a['recovered'] for a in complete)}/{len(complete)}**，另有 {partial} 个对象所在批次触及预算。")
        null=get(fid,"null_test_summary")
        if null:
            summary="，".join(f"{n['candidates']} 条，{len(n['truncated'])} 个截断箱" for n in null["controls"])
            lines.append(f"- {fid} 整夜置换对照为 {summary}。组内相对时间保持，真实时刻与视差的对应关系被打乱。")
        perf=get(fid,"performance_summary")
        if perf and perf["wall_seconds"] is not None:
            lines.append(f"- {fid} 运行 {perf['wall_seconds']:.1f} s，主进程峰值 RSS {perf['max_rss_kib']/1024**2:.2f} GiB，工作目录 {perf['disk_bytes']/1024**3:.2f} GiB。")
    lines.extend(["","注入两组分别指定进入源表的点和假定的噪声、缺测。像素提取、混叠和图像级完整性需要专门实验。","",
                  "Slurm 退出和资源用量见 [记账记录](../logs/slurm-accounting.psv)。初次试点触及压缩 annotated FITS 和选区的内存上限。后续作业采用磁盘暂存和紧凑选区字段。","",
                  "## 边界和验收","",
                  "30–300 au 为工程距离范围。两区的固定时间窗、天空边界、质量掩膜和实际采样共同决定覆盖。短弧轨道和局部协方差可能严重退化。身份核对覆盖 DES 验证目录。完整 MPC 比对、跨季增长、歧义静态全分支、像素级确认和扩大注入仍是验收缺项。",
                  "",
                  "复跑入口见 [运行手册](../docs/operations.md)，其他范围限制见 [限制记录](../docs/limitations.md)。",""])
    (ROOT/"reports"/"v1_report.md").write_text("\n".join(lines))


if __name__=="__main__":
    report()
