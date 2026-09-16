# Nightly build pipeline

source: code:build
scope: the twelve stages of the nightly build, in order
read: 2026-09-15

## In this system

- [verified] Stage 1 of the nightly build fetches the source tree. (build/pipeline.yaml:10)
- [verified] Stage 2 of the nightly build resolves dependencies. (build/pipeline.yaml:20)
- [verified] Stage 3 of the nightly build generates protocol stubs. (build/pipeline.yaml:30)
- [verified] Stage 4 of the nightly build compiles the core library. (build/pipeline.yaml:40)
- [verified] Stage 5 of the nightly build compiles the services. (build/pipeline.yaml:50)
- [verified] Stage 6 of the nightly build runs unit tests. (build/pipeline.yaml:60)
- [verified] Stage 7 of the nightly build runs integration tests. (build/pipeline.yaml:70)
- [verified] Stage 8 of the nightly build builds container images. (build/pipeline.yaml:80)
- [verified] Stage 9 of the nightly build scans images for known vulnerabilities. (build/pipeline.yaml:90)
- [verified] Stage 10 of the nightly build signs the images. (build/pipeline.yaml:100)
- [verified] Stage 11 of the nightly build pushes images to the registry. (build/pipeline.yaml:110)
- [verified] Stage 12 of the nightly build updates the staging manifest. (build/pipeline.yaml:120)
- [verified] A failed stage stops the pipeline and pages the build owner. (build/pipeline.yaml:130)

## Terms

- **Stage**: one named job in the nightly pipeline, run after the previous stage succeeds. (build/pipeline.yaml:5)
- **Staging manifest**: the file that lists which image versions the staging cluster runs. (build/pipeline.yaml:120)

## Open questions

- How long each stage takes. Not in pipeline.yaml.
