from setuptools import find_packages, setup

package_name = 'ch06_action'

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
		'draw_circle_server = ch06_action.draw_circle_server:main',
        'draw_circle_client = ch06_action.draw_circle_client:main',
        ],
    },
)
