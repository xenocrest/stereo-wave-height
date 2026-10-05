import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
from scipy.io import loadmat
from app import core, coordinates
from pipeline.adapters.plane_contract import (COORDINATE_CONTRACT, setup_input,
    unit_plane, require_rigid, require_certified, real_point_metrics)

ROOT = Path('D:/stereo-wave-height-runs/reconstruction-quality-p0-20261001/I12_contract_fixture')

class PlaneContractTests(unittest.TestCase):
    def test_entire_plane_scaling_preserves_equation_and_distance(self):
        raw=np.array([.4,-1.2,.6,-2.5])
        p=unit_plane(raw)
        np.testing.assert_allclose(p,raw/np.linalg.norm(raw[:3]),rtol=1e-15)
        point=np.array([1.,2.,(2.5-.4+2.4)/.6])
        self.assertAlmostEqual(float(p[:3]@point+p[3]),0.)
        self.assertAlmostEqual(np.linalg.norm(p[:3]),1.)

    def test_mean_not_individual_normalization_and_single_row_cli_shape(self):
        raw=np.array([[.1,-.7,.6,4.],[.4,-.6,.7,5.]])
        rows,record=setup_input(raw)
        np.testing.assert_allclose(rows.mean(axis=0),unit_plane(raw.mean(axis=0)))
        self.assertEqual(record['raw_wass_observation_count'],2)
        single,record=setup_input(raw[:1])
        self.assertEqual(single.shape,(2,4))
        self.assertEqual(record['raw_wass_observation_count'],1)
        for p in ([0,0,0,1],[0,0,1,1],[np.nan,1,2,3]):
            with self.assertRaises(ValueError): unit_plane(p)
        with self.assertRaises(ValueError): setup_input(np.vstack([raw[0],-raw[0]]))

    def test_actual_official_setup_real_points_both_datasets(self):
        for label in ('HomeTank','Vieira'):
            root=ROOT/label
            self.assertTrue(root.is_dir(),'run fixes/scripts/validate_i12.py first')
            setup=loadmat(root/'surface/config.mat')
            require_certified(root/'surface/config.mat')
            require_rigid(setup)
            for workspace in sorted((root/'wass/workspaces').glob('*_wd')):
                m=real_point_metrics(setup,workspace)
                self.assertLess(m['camera_grid_camera_error_B']['max'],1e-9)
                for c in m['cameras'].values():
                    self.assertLess(c['reprojection_px']['max'],1e-7)
                    self.assertLess(c['official_forward_matrix_vs_alignment_native']['max'],1e-9)

    def test_legacy_reference_and_run_rejected_before_height(self):
        for label in ('HomeTank21','Vieira0'):
            d=json.loads((core.ROOT/'audit/evidence'/f'{label}.json').read_text('utf-8'))
            old={**d['reference'],**d['identity'],'scientific_run':d['root']}
            with self.assertRaisesRegex(ValueError,'legacy reference'): core.reference_from_metadata(old)
            with patch('app.core.load_frame') as height:
                with self.assertRaisesRegex(ValueError,'REFERENCE_FRAME_MISMATCH'):
                    core.load_result(d['root'],d['frame'],core.reference_from_run(ROOT/('HomeTank' if label.startswith('Home') else 'Vieira')))
                height.assert_not_called()

    def test_missing_or_changed_certificate_rejected(self):
        source=ROOT/'HomeTank/surface'
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            shutil.copy2(source/'config.mat',root/'config.mat')
            with self.assertRaisesRegex(ValueError,'legacy coordinate'):require_certified(root/'config.mat')
            shutil.copy2(source/'coordinate_contract.json',root/'coordinate_contract.json')
            require_certified(root/'config.mat')
            with (root/'config.mat').open('ab') as stream:stream.write(b'changed')
            with self.assertRaisesRegex(ValueError,'changed certified'):require_certified(root/'config.mat')

    def test_reference_and_cache_identifiers_are_versioned(self):
        root=ROOT/'HomeTank'
        ref=core.reference_from_run(root)
        self.assertIn(COORDINATE_CONTRACT,ref.plane_id)
        self.assertEqual(ref.coordinate_contract,COORDINATE_CONTRACT)
        legacy=ref.as_dict();legacy.pop('coordinate_contract')
        with self.assertRaisesRegex(ValueError,'legacy reference'):core.reference_from_metadata(legacy)
        config=core.new_project('x','D:/runs')
        key=core.cache_key(config,21);signature=core.project_input_identity(config)
        with patch('app.core.COORDINATE_CONTRACT','LEGACY'):
            self.assertNotEqual(key,core.cache_key(config,21))
            self.assertNotEqual(signature,core.project_input_identity(config))
        ids=coordinates.identity(root)
        ids['coordinate_contract']='LEGACY'
        with self.assertRaisesRegex(ValueError,'legacy reference/cache'):coordinates.require_match(ref,ids)

if __name__=='__main__':unittest.main()
