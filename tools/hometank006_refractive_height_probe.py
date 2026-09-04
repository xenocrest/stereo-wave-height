"""Conditional refractive stereo experiment; estimated background, NOT validation.

Reference-to-current flow identifies bottom markings, never interpolates height.
Surface points lie on camera rays. At a candidate point both Snell normals must
agree. Unknown absolute background geometry remains an explicit limitation.
No WASS, calibration edits, GUI changes or full-pixel fill.
"""
from pathlib import Path
import argparse
import hashlib
import json
import cv2
import numpy as np
from scipy.optimize import minimize_scalar
from reconstruction.learned_correspondence import TorchvisionRaftCorrespondence
from hometank006_refraction_probe import bottom_intersections

ROOT = Path('D:/stereo-wave-height-runs/HomeTank_006')
CHECKPOINT = Path('D:/stereo-wave-height-runs/tooling/raft_large_C_T_SKHT_V2-ff5fadd5.pth')


class DisCorrespondence:
    """Official OpenCV DIS; alternative bottom tracking, not a height estimator."""
    def _flow(self, a, b):
        model = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
        return model.calc(cv2.cvtColor(a,cv2.COLOR_BGR2GRAY),
                          cv2.cvtColor(b,cv2.COLOR_BGR2GRAY),None).transpose(2,0,1)


def sample(array, uv):
    uv = np.asarray(uv, np.float32).reshape(-1, 2)
    # OpenCV remap destination axes must stay below SHRT_MAX; a flattened
    # 4K query list is longer than this even though its image dimensions are not.
    chunks = []
    for first in range(0, len(uv), 16000):
        q = uv[first:first+16000]
        chunks.append(cv2.remap(array, q[:, 0:1], q[:, 1:2], cv2.INTER_LINEAR,
                      borderMode=cv2.BORDER_CONSTANT, borderValue=float('nan')).reshape(len(q), -1))
    return np.concatenate(chunks) if chunks else np.empty((0, array.shape[2] if array.ndim==3 else 1))


def directions(uv, K):
    v = np.column_stack([uv, np.ones(len(uv))]) @ np.linalg.inv(K).T
    return v/np.linalg.norm(v, axis=1)[:, None]


def background_map(current, reference, model, K, C, n, c, d, mask):
    flow = model._flow(current, reference)
    back = model._flow(reference, current)
    y, x = np.indices(current.shape[:2], dtype=np.float32)
    uv = np.column_stack([x.ravel(), y.ravel()])
    ref_uv = uv + flow.reshape(2, -1).T
    reverse = sample(back.transpose(1, 2, 0), ref_uv)
    valid = np.linalg.norm(flow.reshape(2, -1).T+reverse, axis=1) < 1.5
    valid &= mask.ravel() & (sample(mask.astype(np.float32), ref_uv)[:, 0] > .99)
    P = bottom_intersections(directions(ref_uv, K), C, n, c, d)
    P[~valid] = np.nan
    return P.reshape(*mask.shape, 3).astype(np.float32), valid.reshape(mask.shape)


def snell_normal(air, water, index=1.333):
    n = air-index*water
    return n/np.linalg.norm(n, axis=-1, keepdims=True)


def air_water_entry_valid(air, water, normal):
    """Both directed rays must enter the water side of the oriented interface.

    Tangential Snell equality alone also admits a nonphysical branch, whose
    incoming air ray points OUT of water. Reject it rather than fitting height.
    """
    return (np.sum(air*normal,axis=-1)<0)&(np.sum(water*normal,axis=-1)<0)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--correspondence',choices=['raft','dis','dis_chain'],default='raft')
    parser.add_argument('--target-time',type=int,default=10)
    parser.add_argument('--right-offset',type=float)
    parser.add_argument('--reference-model',type=Path,default=ROOT/'refraction_probe/result.json')
    args=parser.parse_args()
    out = ROOT/('refractive_height_probe' if args.correspondence=='raft' else 'refractive_height_probe_dis')
    if args.correspondence=='dis_chain': out=ROOT/'refractive_height_probe_dis_chain'
    if args.target_time!=10 or args.right_offset is not None:
        out=ROOT/(out.name+f'_t{args.target_time}_offset{args.right_offset}')
    reference_hash=hashlib.sha256(args.reference_model.read_bytes()).hexdigest()
    if args.reference_model.resolve() != (ROOT/'refraction_probe/result.json').resolve():
        out=out.with_name(out.name+'_reference_'+reference_hash[:12])
    out.mkdir(exist_ok=True)
    reference = np.load(ROOT/'surface_chain_raft_centered/frame_01_correspondences.npz')
    # Freeze first static time only; times 2/3 are held out from reference fitting.
    fit = json.loads(args.reference_model.read_text())['frames'][0]['fit']
    n, c, d = np.array(fit['normal']), fit['offset_m'], fit['water_depth_m']
    Ks = [reference[f'P{i}'][:, :3] for i in [0, 1]]
    Cs = [-np.linalg.inv(Ks[i]) @ reference[f'P{i}'][:, 3] for i in [0, 1]]
    # Geometrical common interface domain, not intersection of bottom pixel masks:
    # project each left air-ray intersection with the reference water plane into
    # right camera. A background correspondence must exist there in BOTH views.
    yy0, xx0 = np.indices(reference['left_roi'].shape)
    v0 = directions(np.column_stack([xx0.ravel(), yy0.ravel()]), Ks[0])
    surface0 = Cs[0] - ((Cs[0]@n+c)/(v0@n))[:,None]*v0
    qr = (surface0-Cs[1])@Ks[1].T
    uv_right0 = qr[:,:2]/qr[:,2:3]
    common_reference = (sample(reference['right_roi'].astype(np.float32),uv_right0)[:,0]>.999).reshape(xx0.shape)
    common_reference &= reference['left_roi']
    model = None
    frames = []
    source_run=json.loads((ROOT/'surface_chain_raft_centered/result.json').read_text())
    offset=source_run['offset_candidate_s'] if args.right_offset is None else args.right_offset
    if args.correspondence=='dis_chain' and args.right_offset is None:offset=-.225
    def current_images(time):
        path=ROOT/f'surface_chain_raft_centered/frame_{time:02d}_correspondences.npz'
        if path.exists() and (time!=args.target_time or args.right_offset is None):
            return np.load(path)
        cal=json.loads((ROOT/'rig_features_metric/result.json').read_text())
        rotation=[reference['R0'],reference['R0']@np.array(cal['R']).T]
        images={}
        for i,side in enumerate(['left','right']):
            video=Path('experiments/real_video/HomeTank_006/videos/wave')/f'HomeTank_006_wave_cam{i}_{side.upper()}.mp4'
            cap=cv2.VideoCapture(str(video));cap.set(cv2.CAP_PROP_ORIENTATION_AUTO,0)
            cap.set(cv2.CAP_PROP_POS_MSEC,(time+i*offset)*1000)
            ok,frame=cap.read();pts=cap.get(cv2.CAP_PROP_POS_MSEC)/1000;cap.release()
            if not ok:raise RuntimeError(f'Video decode failed: {video}')
            if i==0:frame=cv2.rotate(frame,cv2.ROTATE_180)
            frame=cv2.resize(frame,(960,540),interpolation=cv2.INTER_AREA)
            maps=cv2.initUndistortRectifyMap(reference[f'K{i}'],reference[f'D{i}'],rotation[i],reference[f'P{i}'],(960,540),cv2.CV_32FC1)
            images[f'rectified_{side}']=cv2.remap(frame,*maps,cv2.INTER_LINEAR)
            print(f'decoded {side} at PTS={pts}',flush=True)
        return images
    for time in [1, 2, 3, args.target_time]:
        cache = out/f'frame_{time:02d}_reference01_background.npz'
        if cache.exists():
            with np.load(cache) as a: maps = [a['left'].copy(), a['right'].copy()]
        else:
            if args.correspondence=='dis_chain' and time==args.target_time:
                raise RuntimeError('Run bottom_tracking_chain.py before chain height evaluation')
            current = current_images(time)
            maps = []
            for i, side in enumerate(['left', 'right']):
                if time == 1:
                    # Exact identity case separates numerical implementation from
                    # cross-frame correspondence failure; NOT an accuracy test.
                    mask = reference[f'{side}_roi']
                    y,x = np.indices(mask.shape)
                    m = bottom_intersections(directions(np.column_stack([x.ravel(),y.ravel()]),Ks[i]),Cs[i],n,c,d)
                    m[~mask.ravel()] = np.nan
                    m = m.reshape(*mask.shape,3).astype(np.float32)
                    valid = np.all(np.isfinite(m),axis=2)
                else:
                    if model is None:
                        model = TorchvisionRaftCorrespondence(CHECKPOINT) if args.correspondence=='raft' else DisCorrespondence()
                    m, valid = background_map(current[f'rectified_{side}'], reference[f'rectified_{side}'],
                                             model, Ks[i], Cs[i], n, c, d, reference[f'{side}_roi'])
                maps.append(m)
                print(f't={time}, {side}: {valid.sum()} reciprocal background correspondences', flush=True)
            np.savez_compressed(cache, left=maps[0], right=maps[1])
        yy, xx = np.where(np.all(np.isfinite(maps[0]), axis=2) & common_reference)
        choose = np.random.default_rng(42).choice(len(xx), min(200, len(xx)), replace=False)
        uv = np.column_stack([xx[choose], yy[choose]])
        rays = directions(uv, Ks[0])
        records = []
        # Search bounds derive from estimated water depth, NOT accepted wave bounds.
        levels = np.linspace(-.9*d, .9*d, 181)
        for pixel, v in zip(uv, rays):
            bg0 = maps[0][pixel[1], pixel[0]].astype(float)
            def evaluate(heights):
                h = np.atleast_1d(heights)
                Q = Cs[0] + ((h-c-Cs[0]@n)/(v@n))[:, None]*v
                vv = Q-Cs[1]; vv /= np.linalg.norm(vv, axis=1)[:, None]
                projection = (Q-Cs[1]) @ Ks[1].T
                pixels = projection[:, :2]/projection[:, 2:3]
                bg1 = sample(maps[1], pixels)
                w0 = bg0-Q; w0 /= np.linalg.norm(w0, axis=1)[:, None]
                w1 = bg1-Q; w1 /= np.linalg.norm(w1, axis=1)[:, None]
                n0, n1 = snell_normal(np.broadcast_to(v, w0.shape), w0), snell_normal(vv, w1)
                error = np.linalg.norm(n0-n1, axis=1)
                valid = (n0@n > 0) & (n1@n > 0) & air_water_entry_valid(v,w0,n0) & air_water_entry_valid(vv,w1,n1)
                return np.where(valid & np.isfinite(error), error, 1e3)
            errors = evaluate(levels)
            k = int(np.argmin(errors))
            if k in [0, len(levels)-1] or errors[k] >= 1e3:
                records.append(dict(uv=pixel.tolist(), status='UNSUPPORTED_NO_INTERIOR_SOLUTION')); continue
            solution = minimize_scalar(lambda h: float(evaluate(h)[0]), bounds=(levels[k-1], levels[k+1]), method='bounded')
            # A broad minimum is not a depth observation. Report range within .01
            # normal-vector discrepancy of minimum (about .57 deg), not accuracy.
            alternatives = levels[errors <= solution.fun+.01]
            span = float(np.ptp(alternatives)) if len(alternatives) else 0.0
            records.append(dict(uv=pixel.tolist(), status=('CONDITIONAL_CANDIDATE' if solution.fun<=2*np.sin(np.deg2rad(1)/2)
                                                          else 'REJECTED_SNELL_INCONSISTENCY'),
                                height_m=float(solution.x), normal_discrepancy=float(solution.fun),
                                near_minimum_height_span_m=span))
        candidates = [r for r in records if r['status']=='CONDITIONAL_CANDIDATE']
        summary = dict(time_s=time, background_counts=[int(np.all(np.isfinite(m), axis=2).sum()) for m in maps],
                       original_left_candidate_pixels=int(reference['left_roi'].sum()),
                       reference_common_interface_pixels=int(common_reference.sum()),
                       available_query_domain_pixels=len(xx),
                       query_count=len(records), conditional_candidates=len(candidates),
                       unsupported_count=len(records)-len(candidates),
                       rejection_counts={s:sum(r['status']==s for r in records) for s in sorted({r['status'] for r in records})})
        if candidates:
            h = np.array([r['height_m'] for r in candidates])
            summary.update(height_median_m=float(np.median(h)), height_p5_p95_m=np.percentile(h, [5,95]).tolist(),
                           height_rms_m=float(np.sqrt(np.mean(h*h))),
                           median_normal_discrepancy=float(np.median([r['normal_discrepancy'] for r in candidates])),
                           median_near_minimum_span_m=float(np.median([r['near_minimum_height_span_m'] for r in candidates])))
        frames.append(summary)
        (out/f'frame_{time:02d}_physical_entry_queries.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        print(json.dumps(summary), flush=True)
    result = dict(status='CONDITIONAL_REFRACTIVE_HEIGHT_NOT_PHYSICALLY_VALIDATED',
                  independent_background_geometry=False, reference=fit,
                  reference_model_path=str(args.reference_model),reference_model_sha256=reference_hash,
                  reference_time_s=1, reference_includes_test_frames=False,
                  normal_agreement_gate_deg=1.0,
                  gate_source='DIAGNOSTIC_ENGINEERING_ASSUMPTION_NOT_ACCURACY_GUARANTEE',
                  air_water_entry_gate=True,
                  correspondence='temporal bottom-marking identity, not temporal height interpolation',
                  correspondence_backend=args.correspondence,
                  target_right_minus_left_offset_s=offset, synchronization_verified=False,
                  search_height_range_m=[float(levels[0]), float(levels[-1])], frames=frames,
                  no_gui_promotion=True, no_full_pixel_claim=True)
    (out/'physical_entry_result.json').write_text(json.dumps(result, indent=2, allow_nan=False), encoding='utf-8')


if __name__=='__main__': main()
