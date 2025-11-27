# * 기능 
# Pinky Pro의 거리 측정 센서로 전방 거리를 측정하다가 
# 20cm 이내에 장애물이 발견되면 해당 장애물 사진을 찍고 해당 사진을 웹 서비스함
# 이 코드에서 개선할 점이 있는데 웹 클라이언트가 주기적으로 서버에 사진 요청을 한다는 것.
# 향후 개선 사항으로, "사건(장애물 발견 후후 사진 촬영)이 발생할 때만 웹 클라이언트로 이미지 전송하도록 기능 개선이 필요.

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2, os, time
from datetime import datetime
from picamera2 import Picamera2
from pinkylib import Ultrasonic
from flask import Flask, Response
import threading

app = Flask(__name__)
latest_jpeg = None   # 최신 이미지를 JPEG로 저장
lock = threading.Lock()

class TakePictureServerNode(Node):
    def __init__(self):
        super().__init__('one_shot_image_web_server')
        self.dist_sensor = Ultrasonic()
        self.bridge = CvBridge()

        # 트리거 조건 관련 변수
        self.prev_condition = False   # 이전 루프에서의 조건 값
        self.current_condition = False
    
        # 저장할 디렉토리
        self.save_dir = '/tmp/ros2_oneshot_images'
        os.makedirs(self.save_dir, exist_ok=True)
        self.get_logger().info(f'Images will be saved to: {self.save_dir}')

        self.init_camera()
        self.timer_start()

    def init_camera(self):
        self.picam2 = Picamera2()
        config = self.picam2.create_still_configuration(
            main={"size": (320, 240), "format": "RGB888"}
        )
        self.picam2.configure(config)
        self.picam2.start()
        time.sleep(1)  # 카메라 워밍업

    def timer_start(self):
        # 주기적으로 조건(장애물 발견)을 폴링할 타이머 (여기서는 0.1ms마다)
        self.timer = self.create_timer(0.1, self.timer_callback)
    def timer_stop(self):
        self.timer.cancel()

    # ---- 이 함수 안에서 "특정 상황"을 if 문으로 구현하면 됨 ----
    def check_condition(self) -> bool:
        dist = self.dist_sensor.get_dist() * 100
        if dist < 20 :
            return True
        else:
            return False

    def timer_callback(self):
        # 1) 현재 조건 계산
        self.current_condition = self.check_condition()
        # 2) False -> True 로 바뀌는 "순간"을 감지 (rising edge detection)
        if (self.prev_condition is False) and (self.current_condition is True):
            self.timer_stop()  # timer 정지
            self.get_logger().info('Trigger condition detected! Taking one shot...')
            self.take_one_shot_web_service()
            self.timer_start()
        # 3) 다음 루프를 위해 현재 값을 prev로 저장
        self.prev_condition = self.current_condition

    def take_one_shot_web_service(self):
        frame_picam2 = self.picam2.capture_array()
        # OpenCV는 BGR을 기대하므로 RGB → BGR 변환
        frame= cv2.cvtColor(frame_picam2, cv2.COLOR_RGB2BGR)
        # 파일 이름 만들기 (시간 기반)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        filename = f'{self.save_dir}/capture_{timestamp}.png'
        # 파일 저장
        cv2.imwrite(filename, frame)
        self.get_logger().info(f'Saved image: {filename}')

        global latest_jpeg
        ret, jpeg = cv2.imencode('.jpg', frame_picam2)
        if not ret:
            self.get_logger().warn('Failed to encode image to JPEG')
            return

        # 전역 변수에 저장 (쓰레드 안전하게)
        with lock:
            latest_jpeg = jpeg.tobytes()

    def destroy_node(self):
        self.picam2.stop()
        super().destroy_node()

@app.route('/')
def index():
    html = """
    <html>
        <head>
            <title>ROS2 Camera Image</title>
        </head>
        <body>
            <h1>Latest Image from ROS2</h1>
            <p>이미지가 안 보이면 /image.jpg 로 직접 접속해서 상태를 확인해보세요.</p>

            <!-- 이미지 태그: id 부여 -->
            <img id="cam_image" src="/image.jpg" style="max-width: 100%;" />

            <script>
                // 주기적으로 이미지 새로고침
                function reloadImage() {
                    const img = document.getElementById('cam_image');
                    const ts = new Date().getTime(); // 캐시 방지를 위한 timestamp
                    img.src = '/image.jpg?ts=' + ts;
                }

                // 500ms(0.5초)마다 새로고침 (원하면 숫자 조절)
                setInterval(reloadImage, 500);
            </script>
        </body>
    </html>
    """
    return html


@app.route('/image.jpg')
def image_jpg():
    with lock:
        if latest_jpeg is None:
            # 아직 이미지가 없을 때
            return "No image received yet.", 503

        return Response(latest_jpeg, mimetype='image/jpeg')

def ros_spin_thread():
    rclpy.init()
    node = TakePictureServerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

def main():
    # ROS2 스핀은 별도 쓰레드에서
    t = threading.Thread(target=ros_spin_thread, daemon=True)
    t.start()
    # Flask 웹 서버 실행
    # host='0.0.0.0' 으로 두면 같은 네트워크의 다른 PC/스마트폰에서도 접속 가능
    app.run(host='0.0.0.0', port=5000, debug=False)

if __name__ == '__main__':
    main()
