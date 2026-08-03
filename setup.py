from glob import glob
import os

from setuptools import find_packages, setup

package_name = 'robot_bag_utils'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # Install all launch files (*.launch.py, *.launch.xml, *.launch.yaml)
        (os.path.join('share', package_name, 'launch'),
            glob(os.path.join('launch', '*launch.[pxy][yma]*'))),

        # Install all configuration YAML files
        (os.path.join('share', package_name, 'config'),
            glob(os.path.join('config', '*.yaml'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Alberto Quattrini Li',
    maintainer_email='Alberto.Quattrini.Li@dartmouth.edu',
    description='TODO: Package description',
    license='MIT',
    tests_require=['pytest', 'launch-testing-ros'],
    entry_points={
        'console_scripts': [
        ],
    },
)
