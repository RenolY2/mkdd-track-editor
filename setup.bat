rem Create and enter a temporary directory.
cd %TMP%
IF EXIST MKDDTE_BUNDLE_TMP rmdir /s /q MKDDTE_BUNDLE_TMP
mkdir MKDDTE_BUNDLE_TMP
cd MKDDTE_BUNDLE_TMP

rem Create a virtual environment.
set PYTHONNOUSERSITE=1
set "PYTHONPATH="
python -m venv venv
call venv/Scripts/activate.bat

rem Install cx_Freeze and its dependencies.
python -m pip install cx-Freeze==6.15.16 cx-Logging==3.2.0 lief==0.14.1

rem Retrieve a fresh checkout from the repository to avoid a potentially
rem polluted local checkout.
git clone https://github.com/RenolY2/mkdd-track-editor.git
cd mkdd-track-editor

rem Install the application's dependencies.
python -m pip install -r requirements.txt

rem Build the bundle.
python setup.py build

rem Open directory in file explorer.
cd build
start .
