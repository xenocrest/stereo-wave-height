"""Artifact-backed audit checks. Never asserts that scientific quality is acceptable."""
import sys,json,unittest,subprocess
from pathlib import Path
from dataclasses import replace
import numpy as np
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import EVIDENCE,RUNS,HROOT,digest
from app import core

def read(name):return json.loads((EVIDENCE/name).read_text('utf-8'))

class EvidenceChecks(unittest.TestCase):
    def test_no_formal_changes(self):
        changed=subprocess.check_output(['git','diff','offline-basic-workflow-ready-v1','--name-only'],cwd=REPO,text=True).splitlines()
        self.assertTrue(all(x.startswith('audit/') for x in changed),changed)
    def test_full_bundle_actual_workspaces(self):
        for label,checks in read('calibration_bundle_provenance.json').items():
            for name,r in checks.items():
                if name.endswith('.xml'):self.assertTrue(r['hash_equal_to_history']);self.assertTrue(r['numeric_equal_to_history'])
                else:self.assertTrue(all(r.values()),name)
    def test_frame_pixel_identity_and_nearest_fixed_left(self):
        for row in read('sync_absolute_pts_and_frame_identity.json')['records']:
            for cam in ['cam0','cam1']:
                matches=[x for x in row['images'][cam] if x['pixel_identical_to_stored']]
                self.assertEqual(len(matches),1,(row['label'],cam,matches))
            self.assertAlmostEqual(row['actual_right_pts_s'],row['nearest_right_for_fixed_left']['pts_s'])
    def test_timestamp_bug_is_reproduced(self):
        p=read('production_pts_regex_reproduction.json')
        for cam in p:self.assertTrue(p[cam]['image_identical_to_original_run']);self.assertEqual(p[cam]['returncode'],0)
        self.assertAlmostEqual(p['cam0']['n0_pts_s'],.0089)
        self.assertNotAlmostEqual(p['cam0']['production_regex_return_value_s'],read('sync_absolute_pts_and_frame_identity.json')['records'][0]['actual_left_pts_s'],places=5)
    def test_official_mapping_and_raw_image_mismatch(self):
        d=read('HomeTank21.json');self.assertLess(d['map_reprojection_error_vs_pixel_centers_px']['quantiles_0_2_50_98_100'][2],.01)
        self.assertGreater(d['gui_raw_alignment_error_px']['quantiles_0_2_50_98_100'][2],4)
    def test_reference_identity_negative(self):
        ref,cal=core.load_reference(HROOT/'reference_plane.json')
        for key in ['calibration_id','extrinsics_id','coordinate_frame_id']:
            wrong=replace(ref,**{key:'AUDIT_NEGATIVE'})
            with self.assertRaisesRegex(ValueError,'REFERENCE_FRAME_MISMATCH'):
                core.load_result(RUNS['HomeTank21'][0],1,wrong,cal)
    def test_nonwater_supported_and_extrapolation(self):
        r=read('actual_XYZ_projection_and_support.json')['HomeTank21']
        self.assertGreater(r['points_projected_into_explicit_ruler_and_upper_backwall_polygons'],99000)
        self.assertEqual(r['grid_outside_hull_finite_count'],r['grid_cells_outside_cloud_XY_convex_hull'])
    def test_grid_isolation_exact_inputs(self):
        r=read('isolated_grid_repeats.json');self.assertEqual(len(r),3)
        self.assertEqual(len({x['cloud_hash'] for x in r}),1);self.assertEqual(len({x['setup_hash'] for x in r}),1)
        z=[x['fixed_grid_z_m']['224,224'] for x in r];self.assertGreater(max(z)-min(z),.005)
    def test_mask_condition_and_failure(self):
        r=read('repeat_and_mask_experiments.json');self.assertEqual([x['case'] for x in r],['repeat1','repeat2','repeat3','mask_A','mask_B'])
        self.assertEqual(r[-1]['status'],'OFFICIAL_FAILURE')
    def test_calibration_orientation(self):
        r=read('calibration_selection_and_orientation.json')
        self.assertEqual(r['left']['opencv_orientation_meta_deg'],180)
        self.assertTrue(r['left']['auto_same_as_native_rot180']);self.assertFalse(r['left']['auto_same_as_native'])
    def test_manifest_existing_file_hashes(self):
        for r in read('artifact_manifest.json'):
            if r['exists']:self.assertEqual(digest(r['path']),r['sha256'],r['path'])
    def test_third_party_historical_hash_guard(self):
        entries=read('third_party_unchanged_guard.json')
        self.assertEqual(len(entries),50)
        for entry in entries:
            self.assertTrue(entry['unchanged'],entry['path'])
            self.assertEqual(digest(entry['path']),entry['baseline_hash'])
    def test_audio_sign_independent_reproduction(self):
        data=read('independent_audio_tlcc.json');normal,reverse=data['fresh_raw_audio_tlcc']
        self.assertEqual(normal['returncode'],0);self.assertEqual(reverse['returncode'],0)
        self.assertAlmostEqual(normal['lag_s'],data['original_offset_s'],places=12)
        self.assertAlmostEqual(reverse['lag_s'],-normal['lag_s'],places=12)
        self.assertFalse(data['physical_exposure_sync_proven'])
    def test_mask_ab_changes_only_official_masks(self):
        root=Path(read('repeat_and_mask_experiments.json')[-1]['path']).parent
        a=(root/'mask_A/stereo_config.txt').read_text('utf-8')
        b=(root/'mask_B/stereo_config.txt').read_text('utf-8')
        b_without_masks='\n'.join(x for x in b.splitlines() if not x.startswith(('LEFT_MASK_IMAGE=water','RIGHT_MASK_IMAGE=water')))
        self.assertEqual(a.strip(),b_without_masks.strip())
        self.assertIn('RANDOM_SEED=20261001',a)
        result=read('mask_AB_retained_outputs.json')
        self.assertEqual(result['mask_B']['preplane_count'],631)
        self.assertFalse(result['mask_B']['filtered_present'])
    def test_real_point_forward_projection_contract_failure(self):
        data=read('actual_XYZ_projection_and_support.json')
        self.assertGreater(data['HomeTank21']['official_alignment_forward_projection_error_px']['quantiles_0_2_50_98_100'][2],.7)
        self.assertLess(data['Vieira0']['official_alignment_forward_projection_error_px']['quantiles_0_2_50_98_100'][2],.003)
        geom=read('geometry_units_and_sensitivity.json')['HomeTank21']
        self.assertGreater(geom['Rpl_orthogonality_frobenius'],.005)
    def test_issue_register_count_and_required_fields(self):
        from collections import Counter
        data=read('issue_registry.json')
        self.assertEqual(data['unique_issues'],15)
        counts=Counter(c for issue in data['issues'] for c in issue['categories'])
        self.assertEqual(dict(counts),data['category_counts']);self.assertEqual(counts['SOFTWARE_BUG'],4)
        self.assertEqual({i['id'] for i in data['issues'] if i['priority']=='P0'},{'I01','I02','I04','I12'})
        required={'evidence','affected_stage','affected_file_function_config','scientific_consequence','proposed_fix_and_test','third_party_modification_required','can_test_now','risk'}
        for issue in data['issues']:self.assertTrue(required.issubset(issue));self.assertTrue(all(issue[k] for k in required))

if __name__=='__main__':unittest.main(verbosity=2)
