import unittest,tempfile,subprocess
from pathlib import Path
import cv2,numpy as np
from tools.vieira_tlcc_sync import parse_source_frame,extract_source_frame,run_checked

class SourcePTSTests(unittest.TestCase):
    def test_join_uses_selected_pts_not_source_n0_or_printed_rounded_time(self):
        log='\n'.join([
            '[showinfo@source @ abc] config in time_base: 1/90000, frame_rate: 60/1',
            '[showinfo@source @ abc] n: 0 pts: 801 pts_time:0.0089',
            '[showinfo@source @ abc] n: 1247 pts: 1890139 pts_time:21.0015',
            '[showinfo@selected @ def] n: 0 pts: 1890139 pts_time:21.0015',
            '[showinfo@source @ abc] n: 1248 pts: 1891638 pts_time:21.0182',
            '[showinfo@selected @ def] n: 1 pts: 1891638 pts_time:21.0182'])
        r=parse_source_frame(log);self.assertEqual(r['source_frame_index'],1247)
        self.assertEqual(r['source_pts_ticks'],1890139);self.assertAlmostEqual(r['actual_source_pts_s'],1890139/90000)

    def test_missing_or_ambiguous_source_fails(self):
        with self.assertRaises(RuntimeError):parse_source_frame('[Parsed_showinfo_0] n:0 pts:801 pts_time:0.0089')
        log='\n'.join(['[showinfo@source @ a] config in time_base: 1/1000',
            '[showinfo@source @ a] n:0 pts:5000 pts_time:5', '[showinfo@source @ a] n:1 pts:5000 pts_time:5',
            '[showinfo@selected @ b] n:0 pts:5000 pts_time:5'])
        with self.assertRaisesRegex(RuntimeError,'ambiguous'):parse_source_frame(log)

    def test_real_ffmpeg_nonzero_start_vfr_and_exact_frame_identity(self):
        ffmpeg=Path('D:/FormatFactory/ffmpeg.exe')
        if not ffmpeg.is_file():self.skipTest('FFmpeg not installed')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);video=root/'source.mkv';out=root/'selected.png';expected=root/'expected.png'
            filter="settb=1/1000,setpts='5000+if(eq(N,0),0,if(eq(N,1),70,if(eq(N,2),230,420)))'"
            run_checked([str(ffmpeg),'-hide_banner','-y','-f','lavfi','-i','testsrc=size=64x48:rate=10',
                '-vf',filter,'-frames:v','4','-vsync','0','-c:v','ffv1',str(video)])
            record=extract_source_frame(ffmpeg,video,5.1,out)
            self.assertEqual(record['source_frame_index'],2);self.assertAlmostEqual(record['actual_source_pts_s'],5.23)
            run_checked([str(ffmpeg),'-hide_banner','-y','-copyts','-i',str(video),'-vf',"select='eq(n,2)'",'-frames:v','1','-vsync','0',str(expected)])
            a=cv2.imdecode(np.fromfile(out,np.uint8),cv2.IMREAD_COLOR);b=cv2.imdecode(np.fromfile(expected,np.uint8),cv2.IMREAD_COLOR)
            np.testing.assert_array_equal(a,b)
            self.assertTrue(Path(record['identification_log']).is_file())

if __name__=='__main__':unittest.main(verbosity=2)
