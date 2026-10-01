# 独立瞬时水面重建质量审计

状态：`INDEPENDENT_RECONSTRUCTION_QUALITY_AUDIT_COMPLETE`。仅完成审计，没有宣布科学质量达标，也没有修正式科学代码。

请先读 [主报告](INDEPENDENT_RECONSTRUCTION_QUALITY_AUDIT_ZH.md)，再读 [问题登记表](ISSUE_REGISTER_ZH.md)、[逐文件数据流](SCIENTIFIC_DATA_FLOW_AUDIT_ZH.md) 和 [官方方法复核](OFFICIAL_METHOD_REVIEW_ZH.md)。主报告覆盖全部17项问题及A–Y回报。

## 实际位置

- Git仓库：`D:/research/stereo-wave-height`，branch `audit/independent-reconstruction-quality`，base `3330a393a1feae5b38f6c589cdde89af8b67d30f`。
- 审计报告/脚本/轻量图像/JSON：仓库 `audit/`。
- 大型诊断：`D:/stereo-wave-height-runs/independent-quality-audit-20261001`。
- 源生产结果：`D:/stereo-wave-height-runs/fixed-coordinate-acceptance-20261001-final/Run_A|Run_B|Run_C/science`；Vieira `D:/stereo-wave-height-runs/pipeline/vieira_official/run_20260928_113344`。
- 最终可交付副本：`C:/Users/徐彻/Documents/Codex/2026-10-01/files-pasted-by-the-user-c/outputs`。`DELIVERY.json`记录实际commit、push、clean和包哈希；避免版本化报告引用自身commit的循环。

`evidence/artifact_manifest.json`记录原科学文件存在性、shape、大小与hash；`external_evidence_manifest.json`记录全部大型诊断文件；`third_party_unchanged_guard.json`核对50份已有历史hash，`installed_scientific_package_source_hashes.json`为当前安装包源码snapshot。后者没有既有baseline，不能伪称有历史前后比较。

## 优先看这些证据

- `HomeTank21_preplane_vs_filtered.png`：plane前已非水面主导。
- `HomeTank21_stages.png`及22/23/Vieira同图：同科学产物、具体时间/帧、支持域和最终显示。
- `HomeTank21_projection_check.png`、`actual_XYZ_projection_and_support.json`：raw错位与前向坐标投影错误分开。
- `*_GUI_cloud.png`、`*_GUI_overlay.png`：同一实际Qt/overlay代码。
- `*_TRUE_SCALE_VIEW.png`及明确`*_VERTICAL_EXAGGERATION_10X.png`：物理轴1:1:1/明确10×；Vieira单位B。
- `HomeTank_fixed_color_scale_comparison.png`：共享H色阶与colorbar。
- `official_mask_AB_preplane_comparison.png`、mask preview及JSON：仅一次官方mask A/B，B失败如实保留。
- `repeat_and_mask_experiments.json`、`isolated_grid_repeats.json`：三次完整重复和三次同cloud孤立grid，不平均。
- `sync_absolute_pts_and_frame_identity.json`、`production_pts_regex_reproduction.json`：真实源PTS、逐像素身份、固定左帧最近右帧及生产regex错误。
- `independent_audio_tlcc.json`：新鲜音频正反顺序独立复算。
- `calibration_selection_and_orientation.json`、`calibration_bundle_provenance.json`：所有50view、K/D、orientation和真实bundle来源。
- `config_comparison.json`及三份config：全部参数有效值diff；`HomeTank_setup_area_grid.png`为官方setup域审查。

三份config的逐字节原件另在`original_config_copies.zip`；Git内TXT仅去除行末空白/结尾空行，以满足`git diff --check`，没有改参数。原件、阅读版各自hash与来源在`config_copy_provenance.json`。所有生产配置文件保持原样。

## 脚本复核

在仓库根目录、PowerShell中：

```powershell
$env:PYTHONIOENCODING='utf-8'
$auditPython = 'D:\stereo-wave-height-runs\wassgridsurface-0.11.4-venv\Scripts\python.exe'
& $auditPython audit/scripts/verify_evidence.py
git diff --check
```

轻量复核顺序（写audit JSON/图和诊断analysis，读原产物；不是修复）：

```powershell
& $auditPython audit/scripts/inspect_artifacts.py
& $auditPython audit/scripts/stage_details.py
& $auditPython audit/scripts/audit_calibration_geometry.py
& $auditPython audit/scripts/render_diagnostics.py
& $auditPython audit/scripts/build_issue_register.py
& $auditPython audit/scripts/config_evidence.py
```

时间复核 `audit_sync.py`解码原视频时间线并验证邻近帧；`audit_audio.py`新提原始音频并用官方FIR/Praat正反算。两者较慢、只写诊断目录。`finalize_evidence.py`用于清单和plot；第一次若缺Vieira诊断，可在独立复制workspace仅启用官方SAVE_FULL_MESH。正式产物不覆盖。

**不要为了“再确认”直接重跑mask实验。** `official_experiments.py`已执行一次mask A/B和三次同输入重复；存在case目录时会拒绝执行。`isolated_grid.py`已执行三次同cloud grid和官方setup检查；仅 `--setup-only`可再次复核官方setup。完整重新做科学诊断需要新的明确实验范围和输出根，避免多次改mask/调参后选择好看结果。

审计脚本中的HomeTank标记21/22/23指request 21/22/23 s；真实左PTS分别21.001544/22.001211/23.000767。图和主报告同时说明历史“21.0089”等时间记录错误。固定pixel用map的(u,v)；固定格点用(row,col)，JSON部分旧key为col,row但本报告224,224无歧义。估计数据未用平均量替代瞬时量。

## 已知记录限制

早期`official_experiments.call`用按序号共享文件名和manifest；随后`isolated_grid`导入同recorder导致前4份console log和原manifest被覆盖。被覆盖的是repeat1三条命令stdout和repeat2的stereo顶层stdout。原workspace `log.txt`、所有科学输出、后续console log未丢失。`legacy_isolated_grid_commands.json`如实保留覆盖后的isolated-grid记录，其中包括第一次无效`generategridconfig`调用；成功setup使用安装版本实际action `generateconfig`，记录在`isolated_grid_commands.json`。

`recovered_experiment_invocations.json`仅从执行过的诊断脚本与现存case目录重建原调用参数，elapsed未知用null、缺失原console用null，不冒充完整原始command recorder。`complete_evidence.py`只整理这些事实和保留mask云，不重新运行mask。recorder已经改为分实验manifest与唯一timestamp日志名。本限制在主报告披露，不影响本报告从保留科学产物核验的计数/XYZ/H证据；不计入被审项目问题数量。

官方最初三角化全云、浮点全量disparity没有现有开关输出；preplane是z-gap后的mesh_full。mask B官方plane失败，没有后续filtered/grid/overlay。现有数据没有独立瞬时高度真值/曝光时序；报告按证据边界保留UNRESOLVED，不通过外观修饰把它们补成正确。
