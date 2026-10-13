import json
from pathlib import Path

from setuptools import find_packages, setup

release = json.loads(Path('release.json').read_text())
setup(
    name='pdfcrowd-cli',
    version=release['version'],
    description='Command-line converters for the PDFCrowd API.',
    long_description=Path('README.md').read_text(),
    long_description_content_type='text/markdown',
    url='https://pdfcrowd.com/api/',
    author='PDFCrowd Team',
    license='MIT',
    python_requires=release['requires_python'],
    package_dir={'': 'src'},
    packages=find_packages('src'),
    package_data={'pdfcrowd_cli': ['command-spec.json']},
    install_requires=[
        f'pdfcrowd>={release["sdk_minimum"]},<{release["sdk_maximum"]}',
        'platformdirs>=4.3.6,<5',
    ],
    entry_points={'console_scripts': [
        'pdfcrowd=pdfcrowd_cli.entrypoints:cli_main',
        'html2pdf=pdfcrowd_cli.entrypoints:html2pdf',
        'html2image=pdfcrowd_cli.entrypoints:html2image',
        'image2image=pdfcrowd_cli.entrypoints:image2image',
        'pdf2pdf=pdfcrowd_cli.entrypoints:pdf2pdf',
        'image2pdf=pdfcrowd_cli.entrypoints:image2pdf',
        'pdf2html=pdfcrowd_cli.entrypoints:pdf2html',
        'pdf2text=pdfcrowd_cli.entrypoints:pdf2text',
        'pdf2image=pdfcrowd_cli.entrypoints:pdf2image',
    ]},
)
