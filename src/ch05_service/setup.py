from setuptools import find_packages, setup

package_name = 'ch05_service'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='felix',
    maintainer_email='felix@todo.todo',
    description='TODO: Package description',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
		'led_server  = ch05_service.led_server:main',
        'led_client  = ch05_service.led_client:main',

        'battery_color_service = ch05_service.battery_color_service_node:main',
	'sensor_reset_server = ch05_service.sensor_reset_server:main',
'sensor_reset_client = ch05_service.sensor_reset_client:main',
        ],
    },
)
