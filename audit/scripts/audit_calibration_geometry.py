"""Calibration metadata, image orientation, pose, units and geometric sensitivity."""
import sys,json,subprocess,hashlib
from pathlib import Path
import cv2,numpy as np
from scipy.io import loadmat
from plyfile import PlyData
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO),str(REPO/'src')]
from audit.scripts.inspect_artifacts import ROOT,RUNS,dump,stats,digest,project
from pipeline.adapters.wass import load_matrix
from wassgridsurface.wass_utils import load_camera_mesh

def main():
    ROOT.mkdir(parents=True,exist_ok=True)
    fresh=Path('D:/stereo-wave-height-runs/pipeline/hometank004/run_20260928_113734/calibration')
    rows={}
    for camera in ['left','right']:
        folder=fresh/camera;r=json.loads((folder/'calibration.json').read_text('utf-8'))
        selected=[x for x in r['all_detections'] if x['frame_index'] in r['selected_frame_indices']]
        corners=np.vstack([x['corners_px'] for x in selected]).astype(np.float32)
        w,h=r['image_size_wh'];hull=cv2.convexHull(corners)
        filehashes=[digest(folder/x) for x in r['selected_frame_files']]
        row={k:r[k] for k in ['source_video','image_size_wh','fps_reported_by_decoder','pattern_inner_corners','square_size_m','complete_detection_count','selected_view_count','selected_frame_indices','rms_px','camera_matrix','distortion_k1_k2_p1_p2_k3']}
        row.update(per_view_errors=stats(r['per_view_rms_px']),sharpness=stats([x['sharpness_laplacian_variance'] for x in selected]),corner_xy_min=corners.min(0).tolist(),corner_xy_max=corners.max(0).tolist(),corner_hull_fraction=float(cv2.contourArea(hull)/(w*h)),selected_duplicate_hash_count=len(filehashes)-len(set(filehashes)),board_center_x=stats([x['descriptor'][0] for x in selected]),board_center_y=stats([x['descriptor'][1] for x in selected]),perspective_descriptor=stats([x['descriptor'][-1] for x in selected]))
        video=r['source_video'];cap=cv2.VideoCapture(video);cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0);cap.set(cv2.CAP_PROP_POS_FRAMES,r['selected_frame_indices'][0]);ok,native=cap.read();cap.release()
        cap=cv2.VideoCapture(video);rotation=cap.get(cv2.CAP_PROP_ORIENTATION_META);cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,1);cap.set(cv2.CAP_PROP_POS_FRAMES,r['selected_frame_indices'][0]);ok,automatic=cap.read();cap.release()
        row['opencv_orientation_meta_deg']=rotation
        row['auto_same_as_native']=bool(np.array_equal(native,automatic));row['auto_same_as_native_rot180']=bool(np.array_equal(cv2.rotate(native,cv2.ROTATE_180),automatic))
        preview=cv2.resize(np.hstack((native,automatic)),(1280,360))
        cv2.putText(preview,'Calibration native | default auto-rotation',(20,30),cv2.FONT_HERSHEY_SIMPLEX,.6,(0,0,255),2)
        cv2.imwrite(str(REPO/'audit/evidence'/f'{camera}_calibration_orientation.png'),preview)
        rows[camera]=row
    dump('calibration_selection_and_orientation.json',rows)
    geo={}
    for label,(root,frame) in RUNS.items():
        ws=root/'wass/workspaces'/f'{frame:06d}_wd';setup=loadmat(root/'surface/config.mat');mesh=load_camera_mesh(ws/'mesh_cam.xyzC')
        baseline=setup['CAM_BASELINE'].item();f=float(setup['K1'][0,0]);depth=mesh[2]*baseline
        centers=[]
        for cam in [0,1]:
            P=np.loadtxt(ws/f'P{cam}cam.txt');R=np.linalg.inv(setup[f'K{cam}'])@P[:,:3];t=np.linalg.inv(setup[f'K{cam}'])@P[:,3];centers.append(-np.linalg.solve(R,t))
        a=mesh.T-centers[0];b=mesh.T-centers[1]
        a/=np.linalg.norm(a,axis=1)[:,None];b/=np.linalg.norm(b,axis=1)[:,None]
        angle=np.degrees(np.arccos(np.clip((a*b).sum(1),-1,1)))
        Rpl=setup['Rpl'];sv=np.linalg.svd(Rpl,compute_uv=False)
        ply=PlyData.read(ws/'mesh.ply')['vertex'].data;xyz=np.vstack([ply[n] for n in ('x','y','z')])
        row={'baseline_unit': 'm' if label.startswith('HomeTank') else 'B', 'applied_baseline':baseline,'extrinsic_T':load_matrix(root/'wass/config/ext_T.xml').flatten().tolist(),'extrinsic_norm':float(np.linalg.norm(load_matrix(root/'wass/config/ext_T.xml'))),'normalized_camera_center_distance':float(np.linalg.norm(centers[0]-centers[1])),'camera_depth_native':stats(depth),'true_triangulation_angle_deg':stats(angle),'Rpl_orthogonality_frobenius':float(np.linalg.norm(Rpl.T@Rpl-np.eye(3))),'Rpl_determinant':float(np.linalg.det(Rpl)),'Rpl_singular_values':sv.tolist(),'camera_mesh_vs_ply_coordinate_distance_B':stats(np.linalg.norm(mesh-xyz,axis=0)), 'focal_px_for_ideal_parallel_sensitivity':f}
        depths=np.percentile(depth,[2,50,98])
        row['ideal_parallel_sensitivity_not_real_error']=[{'depth_native':float(z),'equivalent_disparity_px':float(f*baseline/z),'depth_change_for_disparity_error':{str(e):float(z*z/(f*baseline)*e) for e in [1,.5,.2]}} for z in depths]
        geo[label]=row
    dump('geometry_units_and_sensitivity.json',geo)
    # Exact production extraction invocation: demonstrate what its n=0 regex selects.
    s=json.loads((RUNS['HomeTank21'][0]/'sync/sync.json').read_text('utf-8'));ptsprobe={}
    for camera,key in [('cam0','left'),('cam1','right')]:
        target=s['frame_mapping'][1][key+'_requested_timestamp_s'];out=ROOT/f'{camera}_production_extract_probe.png'
        argv=[s['ffmpeg'],'-hide_banner','-loglevel','info','-y','-i',s[key+'_video'],'-ss',f'{target:.9f}','-vf','showinfo','-frames:v','1','-vsync','0',str(out)]
        p=subprocess.run(argv,capture_output=True,text=True,encoding='utf-8',errors='replace');log=ROOT/f'{camera}_production_extract_showinfo.log';log.write_text(p.stderr,encoding='utf-8')
        import re
        m=re.search(r'\bn:\s*0\s+pts:\s*-?\d+\s+pts_time:\s*([-+0-9.eE]+)',p.stderr)
        ptsprobe[camera]={'argv':argv,'returncode':p.returncode,'n0_pts_s':float(m.group(1)), 'production_regex_return_value_s':target+float(m.group(1)),'image_identical_to_original_run':bool(np.array_equal(cv2.imread(str(out)),cv2.imread(s['frame_mapping'][1][key+'_file']))),'showinfo_log':str(log)}
    dump('production_pts_regex_reproduction.json',ptsprobe)
    print(json.dumps({'calibration':{k:{q:rows[k][q] for q in ['rms_px','opencv_orientation_meta_deg','auto_same_as_native_rot180','corner_hull_fraction']} for k in rows},'geometry':{k:{q:geo[k][q] for q in ['camera_depth_native','true_triangulation_angle_deg','Rpl_orthogonality_frobenius','Rpl_determinant']} for k in geo},'ptsprobe':ptsprobe},ensure_ascii=False))

if __name__=='__main__':main()
