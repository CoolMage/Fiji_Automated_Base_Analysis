# Example datasets

The `sample_documents` folder demonstrates the naming conventions used by the
Fiji Document Processor. The files are tiny text placeholders that mimic how a
real study might be organised:

```
sample_documents/
├── Experiment_A
│   ├── 01_Control_MIP.tif
│   ├── 01_Control_MIP.roi
│   ├── 02_4MU_pre.tif
│   └── 02_4MU_pre.zip
└── Experiment_B
    ├── 03_Control_post.tif
    ├── 03_Control_post_RoiSet.zip
    └── 04_4MU_followup.tif
```

Try these commands from the repository root to explore different scenarios:

```bash
# Match a single keyword
python main.py examples/sample_documents --keyword 4MU --verbose

# Match multiple keywords and apply ROIs
python main.py examples/sample_documents --keyword 4MU --keyword Control --apply-roi \
    --roi-template "{name}.roi" --roi-template "{name}_RoiSet.zip" --verbose

# Enforce a secondary filter and save processed output
python main.py examples/sample_documents --keyword Control --secondary-filter MIP \
    --save-processed --suffix demo --measurement-prefix example_run --verbose
```

Feel free to duplicate the folder and rename files to mirror your real-world
experiments. Every option surfaced by `main.py --help` maps directly to a field
in `ProcessingOptions` so you can experiment from the command line before
embedding the processor in larger scripts.
