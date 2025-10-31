from pinkylib import IR, Motor, Buzzer
import time

def end_processor():
	motors.stop()
	motors.disable_motor()
	motors.close()
	ir_sensors.close()
	buzzer.clean()
	print('주행을 종료합니다.')

buzzer = Buzzer()
ir_sensors = IR()			# line detection sensor를 처리할 객체 생성
motors = Motor()			# 모터를 처리할 객체 생성
motors.enable_motor()		# 모터 활성화
base_speed = 74				# 속도
speed_up = 0				# 직선 구간인 경우 속도 증가

buzzer.buzzer_start()		# 주행의 시작을 알리기 위해
buzzer.buzzer(2, duration=0.2)				# 띠.띠.띠~
buzzer.buzzer(1, duration=1)
buzzer.buzzer_stop()

start_time = time.time()	# 완주 시간을 측정하기 위해 주행 시작할 때 시간을 저장

while True:
	try:
		left, middle, right = ir_sensors.read_ir()
		#print(f"left:{left}, middle: {middle}, right: {right}")
		if left > 2800 and middle > 2800 and right > 2800:
			print('Pinky Pros는 주행을 종료합니다!')
			break

		total = (left + middle + right)
		R_speed = int( (middle + left) / total * base_speed )
		L_speed = int( (middle +right) / total * base_speed )

		# print('diff:', L_speed - R_speed)
		# 직선 구간에서 가속			
		speed_up = speed_up + 0.5 if abs(L_speed - R_speed) < 4 else  0
		R_speed = R_speed + int(speed_up)
		L_speed = L_speed + int(speed_up)
		R_SPEED = 100 if R_speed > 100 else R_speed
		L_SPEED = 100 if L_speed > 100 else L_speed

		#print(L_SPEED, '\t', R_SPEED)
		motors.move(L_SPEED, R_SPEED)

	except:
		end_processor()

print(f'경과 시간 : { time.time() - start_time :.2f}[s]')
buzzer.buzzer_start()		# 주행의 시작을 알리기 위해
buzzer.buzzer(2, duration=0.2)				# 띠.띠.
buzzer.buzzer_stop()
end_processor()


