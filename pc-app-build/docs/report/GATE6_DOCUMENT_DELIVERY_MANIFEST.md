# Gate 6 Document Delivery Manifest

基线：`2bd25c3677cf2aecd2784d089e8f971c40bb377e`  
用途：纯文档覆盖包，不包含生产代码、模型、真实配置或测试通过声明。

## Updated

- `docs/PC_ASSISTANT_RUNTIME_MASTER_PLAN.md`
- `docs/spec/gate5/GATE5_SPEC_INDEX.md`
- `docs/report/GATE5_FINAL_ACCEPTANCE_REPORT.md`

## Added

- `docs/spec/gate6/GATE6_SPEC_INDEX.md`
- `docs/spec/gate6/GATE6_ANDROID_REFERENCE_AUDIT.md`
- `docs/spec/gate6/GATE6_AUDIO_DEVICE_KWS_AEC_BARGE_IN_SPEC.md`
- `docs/spec/gate6/GATE6_IMPLEMENTATION_PLAN.md`
- `docs/spec/gate6/GATE6_TEST_AND_ACCEPTANCE_PLAN.md`
- `docs/spec/gate6/GATE6_SPEC_MANIFEST.json`
- `docs/adr/ADR-010-gate6-cross-platform-audio-session.md`
- `docs/amendments/PC_ASSISTANT_RUNTIME_MASTER_PLAN_GATE6_AMENDMENT.md`
- `docs/report/GATE6_0_PROBE_REPORT_TEMPLATE.md`
- `docs/report/GATE6_DOCUMENT_DELIVERY_MANIFEST.md`

## Frozen conclusions

- Gate 5 accepted on user-reported Windows Automated/Fake/Real evidence；
- Gate 5 tool count 32；
- Gate 6.5 merged into Gate 6；
- five phases: 6.0～6.4；
- device/duplex -> KWS -> AEC/NS -> acoustic barge-in；
- AEC automatic、NS conservative、AGC off；
- no raw-mic speaker-route barge-in fallback；
- minimal Voice & Devices sheet, no full settings center；
- `Accepted-Windows` and `Accepted-CrossPlatform` separate；
- concrete AEC backend pending Gate 6.0 Real probe。

## Explicit non-claims

- 未执行 Gate 6 代码或测试；
- 未选择最终 AEC backend；
- 未宣称 macOS 已通过；
- 未包含或修改现有生产源码；
- 未包含 PCM/Opus/model/token/identity/log。

