from setuptools import find_packages, setup
import os
from glob import glob
package_name = 'ch07_params'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
	# 安装 config 目录下所有 YAML 文件
    (os.path.join('share', package_name, 'config'),
        glob('config/*.yaml')),
    # 安装 launch 文件
    (os.path.join('share', package_name, 'launch'),
        glob('launch/*.launch.py')),
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
	'battery_node=ch07_params.battery_node:main',
        ],
    },
)
