import unittest,tempfile,json
from pathlib import Path
from unittest.mock import patch,MagicMock
import cv2,numpy as np
from tools.camera_image import open_canonical_video,orientation_metadata,CANONICAL_CAMERA_IMAGE_ORIENTATION
from tools.vieira_tlcc_sync import extract_source_frame
from app import core

class CanonicalOrientationTests(unittest.TestCase):
    def test_orientation_is_explicit_not_backend_default(self):
        capture=MagicMock();capture.isOpened.return_value=True;capture.set.return_value=True
        with patch('tools.camera_image.cv2.VideoCapture',return_value=capture):
            self.assertIs(open_canonical_video('test.mp4'),capture)
            capture.set.assert_called_once_with(cv2.CAP_PROP_ORIENTATION_AUTO,1)
        capture.set.return_value=False
        with patch('tools.camera_image.cv2.VideoCapture',return_value=capture):
            with self.assertRaisesRegex(ValueError,'cannot explicitly honor'):open_canonical_video('test.mp4')

    def test_real_calibration_preview_wave_and_ffmpeg_same_orientation(self):
        root=core.ROOT/'experiments/real_video/HomeTank_004/videos';ffmpeg=Path('D:/FormatFactory/ffmpeg.exe')
        videos=list((root/'calibration').glob('*.mp4'))+list((root/'wave').glob('*.mp4'))
        if len(videos)!=4 or not ffmpeg.is_file():self.skipTest('Real original videos/FFmpeg not installed')
        with tempfile.TemporaryDirectory() as directory:
            for video in videos:
                capture=open_canonical_video(video);info=orientation_metadata(capture);ok,image=capture.read();capture.release()
                self.assertTrue(ok);self.assertTrue(info['opencv_orientation_auto'])
                self.assertEqual(info['canonical_camera_image_orientation'],CANONICAL_CAMERA_IMAGE_ORIENTATION)
                preview=core.read_preview(str(video),0)
                np.testing.assert_array_equal(preview,cv2.cvtColor(image,cv2.COLOR_BGR2RGB))
                out=Path(directory)/(video.stem+'.png');record=extract_source_frame(ffmpeg,video,0.,out)
                decoded=cv2.imdecode(np.fromfile(out,np.uint8),cv2.IMREAD_COLOR)
                self.assertEqual(decoded.shape,image.shape)
                # Independent decoder builds can round YUV→RGB differently;
                # validate orientation and a tight pixel agreement, not identity
                # of numerical calibration across different decoder versions.
                self.assertLess(float(np.abs(decoded.astype(float)-image).mean()),2.)
                self.assertEqual(record['canonical_camera_image_orientation'],CANONICAL_CAMERA_IMAGE_ORIENTATION)
                self.assertEqual(record['source_frame_index'],0)

if __name__=='__main__':unittest.main(verbosity=2)
