# 구매 파이프라인의 입출력과 품질 검사

이 시스템은 공급처별 재고와 이력을 분석한 뒤 구매 분석보고서, 발주요청서, 공급처 이메일 초안을 구성합니다. 분석 모델이 내놓는 결과는 품목 코드와 근거 번호가 별도로 담긴 JSON입니다. 코드와 검사 모델이 이 결과를 검사한 뒤, 코드가 표와 문장을 조립해 Word 파일을 만듭니다.

아래의 입력·응답 예시는 합성 데이터로 실행한 MeridianSeals 사례를 사용합니다. 길이를 줄이기 위해 JSON 예시에는 확인할 필드와 일부 항목만 발췌했습니다. 코드가 만드는 입력은 사례 CSV와 이력, 실행 기록에 저장된 분석 결과로 재구성했습니다. [사례 입력](../dev/cases/meridian_seals_walkthrough.json) · [실행 기록](../dev/runs/2026-11-19_115421_walkthrough-sample-one-record-entry-per-agent/record.json)

## CSV에서 Word까지

```text
재고 CSV
  → 코드가 유효한 행을 공급처별로 묶고 재고 수치·날짜를 계산
  → 조회한 이력 원문과 함께 분석 모델에 JSON으로 전달
  → 분석 응답 JSON을 코드와 분석 Judge가 검사
  → 코드가 분석보고서를 조립
  → 발주 대상이 있으면 발주요청서와 이메일을 병렬로 작성·검사
  → Word 초안과 검토 메모를 구성
```

CSV에서 `ItemCode`는 품목의 식별자, `ItemName`은 품목명, `SupplierName`은 공급처명입니다. `SnapshotDate`와 `AvailableStock`, `WksToOOS`를 바탕으로 기본 조달 기간 18주 기준의 위험도, 재고 공백, 권장 수량, 최종 발주일과 요청 납기를 계산합니다. 분석 입력에는 이 전처리를 마친 **한 공급처의 품목 목록**이 들어갑니다. 코드가 이 공급처와 품목들의 이력을 조회하고, 선택한 문서 원문을 같은 JSON에 담습니다. [CSV 전처리](../utils/csv_utils.py#L143) · [품목 묶음과 수치 계산](../services/item_grouping.py#L374) · [분석 입력 조립](../services/agents.py#L239)

분석 후 조달 기간을 반영한 위험도가 Critical, High 또는 Medium인 품목이 발주 대상입니다. 대상이 있으면 두 작성 모델은 각각 선택된 분석 결과와 코드가 준비한 데이터를 사용합니다. Word 분석보고서의 품목표, 발주요청서의 품목표·출처·결재란, 이메일의 인사·목적·품목 목록·맺음말·서명은 코드가 조립합니다. [발주 대상 선택](../services/documents.py#L85) · [문서 생성 그래프](../services/agents.py#L628)

## 각 모델 호출의 입력과 응답

`system` 메시지는 모델의 역할과 작성·검사 지시를 담습니다. `user` 메시지는 처리할 데이터입니다. 작성 모델에는 프롬프트로 JSON을 요구하고 코드가 응답 텍스트에서 JSON을 읽습니다. 세 Judge에는 판정 표를 설명한 프롬프트와 함께 API 수준의 JSON 스키마도 지정합니다. [작성 호출](../services/agents.py#L227) · [Haiku Judge 호출](../services/quality_checks.py#L574)

| 호출 | 어떤 형태로 무엇을 보냄 | 어떤 형태로 받고 어떻게 사용함 |
|---|---|---|
| 구매 분석 | `system`에 분석 프롬프트, `user`에 `snapshot_date`·`supplier`·`items`·`history`를 담은 JSON 1개 | 분석 JSON을 파싱해 품목 코드, 근거 번호, 변경 제안, 질문, 조치, 요약을 읽고 검사를 실행 |
| 분석 재작성 | 기존 분석 `system` 지시와 원래 `user` 입력 JSON, `assistant` 메시지로 직전 분석 JSON, 새 `user` 메시지로 실패 항목과 사유 | 같은 구조의 전체 분석 JSON을 다시 받음. 파싱할 수 없는 재작성 응답의 경우 직전 분석을 유지 |
| 분석 Judge | `system`에 공통 판정 지시, `user`에 `INPUTS`·`AI OUTPUT`·`CHECKS`로 구획한 텍스트 | 적용 검사 ID별 근거·참/거짓·실패 메모를 담은 JSON을 읽어 코드 검사 결과와 합침 |
| 발주요청서 작성 | `system`에 발주요청서 프롬프트, `user`에 공급처, 주문 품목과 수치, 인용 가능한 확인 사실, 변경·조치를 담은 JSON | `purpose`와 `justification`을 담은 JSON을 파싱해 Word의 두 문단에 사용 |
| 발주요청서 Judge | 공통 판정 지시와 `INPUT GIVEN TO THE WRITER`·`TEXT WRITTEN`·`CHECKS`로 구획한 텍스트 | P1a–c 판정 JSON을 받아 P2·P3 코드 결과와 합침 |
| 이메일 작성 | `system`에 이메일 프롬프트, `user`에 공급처, 주문 품목·수량·납기와 확인할 사항 등을 담은 JSON | `requests` 문단을 담은 JSON의 응답 텍스트를 보관하고, 검사와 문서 조립 시 `requests`를 읽음 |
| 이메일 재작성 | 이메일 프롬프트에 내부 정보 보호 지시를 추가. `user`에 작성 때와 같은 JSON 뒤에 노출 검사 실패 사유와 재작성 요청을 붙인 한 메시지 | 새 `requests` JSON을 받아 노출 검사를 다시 실행 |
| 이메일 노출 검사 | 코드가 먼저 내부 용어 및 주문 외 품목을 검사. 여기서 통과하면 문의 문장, 주문 외 품목명 목록, 검사 지시를 한 텍스트 메시지로 보냄 | `PASS` 또는 `FAIL: <사유>` 텍스트를 받아 한 초안에 대한 통과 여부와 재작성 사유를 생성 |
| 이메일 품질 Judge | 공통 판정 지시와 `INPUT GIVEN TO THE WRITER`·`REQUESTS WRITTEN`·`CHECKS`로 구획한 텍스트 | E4–E7 판정 JSON을 받아 마지막 문의 문단의 검토 메모에 사용 |

작성·재작성 호출에서는 입력을 조립하는 코드, 프롬프트에 명시된 요구, 응답을 처리하는 코드가 각각 관여합니다. 다음 절에서 이 세 위치를 실제 필드 이름으로 연결합니다. [분석 재작성](../services/agents.py#L363) · [이메일 작성·검사](../services/agents.py#L497) · [판정 프롬프트](../services/quality_checks.py#L472)

### 구매 분석의 입력

원본 재고 CSV의 BushingSleeve 행은 다음과 같습니다. [입력 CSV](../dev/cases/meridian_seals_walkthrough.json#L5)

```csv
ItemCode,ItemName,SupplierName,AvailableStock,WksToOOS
610001,BushingSleeve,MeridianSeals,500,10
```

코드는 행을 공급처별로 묶고 품목별 재고 지표를 계산합니다. 분석 모델에게 보내는 `items`에는 품목 코드·품목명, 가용 재고, 소진까지 남은 주수, 기본 위험도·재고 공백, 권장 수량, 권장 발주·납기와 시급도 문구가 들어갑니다. `history`에는 문서 번호, 문서가 적용되는 공급처와 품목명·코드, 작성일, 원문이 들어갑니다. 모델은 문서 번호를 인용하고 코드는 그 번호를 원본 출처에 연결합니다. [분석 프롬프트의 INPUT](../prompts/analysis.md#L20) · [이력 필드 구성](../services/agents.py#L155)

```json
{
  "snapshot_date": "2025-04-05",
  "supplier": "MeridianSeals",
  "items": [
    {
      "item_code": "610001",
      "item_name": "BushingSleeve",
      "available_stock": 500,
      "wks_to_oos": 10,
      "risk_level": "Critical",
      "expected_stockout_weeks": 8,
      "suggested_quantity": 1300,
      "recommended_latest_po_date": "2025-04-05",
      "recommended_latest_delivery_date": "2025-06-14"
    }
  ],
  "history": [
    {
      "id": 1,
      "supplier": "MeridianSeals",
      "items": [],
      "item_codes": [],
      "date": "2025-03-12",
      "text": "MeridianSeals announced that from 1 April 2025 lead times for all products are four weeks longer while a moulding line is refitted; the supplier expects this to last until the end of 2025."
    }
  ]
}
```

문서 1의 `items`·`item_codes`가 빈 배열이고 `supplier`가 MeridianSeals이므로 그 문서는 공급처 전체에 적용됩니다. 이처럼 **문서의 적용 대상**이 원문과 함께 입력으로 들어갑니다. [이력 적용 범위 지시](../prompts/analysis.md#L60)

### 이력 조회 범위와 문서 번호

한 공급처를 분석할 때, 코드는 문서 헤더에 있는 공급처명 또는 분석 대상의 품목명·코드로 후보를 찾습니다. 다른 공급처가 명시된 문서는 제외합니다. 날짜 범위는 시작일 초과부터 재고 기준일 이하까지입니다. 시작일은 기본 12개월 전으로, 일자는 재고 기준일의 일자를 최대 28일로 제한해 계산합니다. 날짜 필터와 정렬에는 문서 날짜를 쓰고, 날짜를 읽을 수 없는 문서는 저장일을 씁니다. 이때 모델 입력의 문서 `date`는 빈 문자열로 남습니다. [조회 날짜와 범위 계산](../services/vector_store.py#L257) · [조회 기본값](../config.py#L42) · [모델 입력의 문서 필드](../services/agents.py#L155)

| 조회 범위 | 5건을 적용하는 단위 | 예시 |
|---|---|---|
| 현재 공급처 관련 | 공급처당 한 번 | MeridianSeals 전체에 관한 이력과, MeridianSeals의 품목 중 이번 분석 목록에 없는 품목 이력 |
| 현재 공급처의 특정 품목 | 분석 대상 품목마다 한 번 | MeridianSeals가 공급한 BushingSleeve 이력 최대 5건, MeridianSeals가 공급한 GasketRing 이력 최대 5건 |
| 특정 품목 공통 | 분석 대상 품목마다 한 번 | 공급처가 명시되지 않은 BushingSleeve 이력 최대 5건, 공급처가 명시되지 않은 GasketRing 이력 최대 5건 |

따라서 품목이 하나인 공급처에는 최대 `5 + 5 + 5 = 15건`을 보낼 수 있습니다. 분석 대상이 두 품목이면 최대 25건이며, 일반식은 `5 × (1 + 2 × 분석 품목 수)`입니다. 각 범위에서 날짜가 최신인 5건을 먼저 고른 뒤, 여러 범위에 잡힌 같은 문서는 한 번만 남깁니다. 범위에 들어온 문서 수나 중복 여부에 따라 실제 전달 건수는 달라집니다. [범위별 선택과 중복 제거](../services/vector_store.py#L320)

선택을 마치면 **합친 문서 전체를 날짜 최신순으로 정렬**합니다. 날짜가 같은 문서들은 합친 목록의 상대 순서를 유지합니다. 그 목록을 분석 모델에 보낼 단일 JSON의 `history` 배열에 넣고, 앞에서부터 `id: 1`, `id: 2`처럼 번호를 붙입니다. 예를 들어 4월 1일 품목 공통 이력, 3월 20일 공급처 이력, 3월 12일 해당 공급처의 품목 이력이 선택되면 날짜순으로 각각 1·2·3번이 됩니다. 공급처 이력과 품목 이력이 한 배열 안에서 섞일 수 있습니다. 첫 번째 문서에서 확인한 사실은 응답의 `basis.documents: [1]`로 인용하고, 코드가 같은 순서의 출처 목록을 사용해 이를 Word 보고서의 원문에 연결합니다. [정렬과 반환](../services/vector_store.py#L331) · [모델에 전달할 ID 부여](../services/agents.py#L155) · [판정 프롬프트의 문서 번호](../services/quality_checks.py#L482)

이 문서의 MeridianSeals 예시는 개발용 실행입니다. 이 실행은 사례 파일의 `history` 배열을 그대로 공급하므로, 배열에 놓인 조달 기간 공지·통관 보류 이력·OilRing 검토 문서가 차례로 1·2·3번입니다. 운영에서 조회한 목록의 날짜순 번호와 비교할 때는 개발 사례의 원래 배열 순서를 기준으로 봅니다. [개발 사례 전달](../scripts/run_dev_case.py#L67) · [개발 이력 입력 처리](../services/agents.py#L191) · [실제 사례 배열](../dev/cases/meridian_seals_walkthrough.json)

### 구매 분석의 응답과 C2 검사 위치

분석 프롬프트는 아래 필드만 지정된 순서로 담은 JSON을 요구합니다. 재고에서 나온 사실은 모델 응답의 `stock_findings`에 따로 들어오고, 파싱 직후 코드가 `findings`와 합칩니다. `references`는 코드가 붙이는 문서 출처입니다. [분석 프롬프트의 OUTPUT](../prompts/analysis.md#L75) · [응답을 코드에서 쓰는 형태로 변환](../services/agents.py#L201)

| 응답 필드 | 값과 코드에서 쓰는 위치 |
|---|---|
| `findings` | 이력에서 확인한 사실 목록. 항목마다 `id`, 관련 품목 코드 배열 `items`, 사실 문장 `text`, 근거 출처 `basis` |
| `supplier_lead_time` | 공급처 전체 조달 기간 제안 객체 또는 `null`. 기간, 사유, 인용한 사실 번호 |
| `lead_time_changes` | 품목별 조달 기간 변경 배열. 관련 품목 코드 배열, 최종 기간, 사유, 인용한 사실 번호 |
| `quantity_changes` | 품목별 수량 변경 배열. `item_code`, 기존 수량, 배율, 제안 수량, 사유, 인용한 사실 번호 |
| `figures_after_changes` | 조달 기간 변경 품목별로 모델이 계산한 조달 기간, 위험도, 공백, 최종 발주일. C10에서 코드 계산값과 대조 |
| `stock_findings` | 재고 수치에서 나온 사실 배열. `basis.stock`을 `true`로 표시하고 문서 번호 배열은 비워 둠 |
| `critical_questions` | 확인 질문 배열. 질문 문장 `question`, 답할 주체 `ask`, 관련 품목 코드 배열 `items`, 인용한 사실 번호 `findings` |
| `recommended_actions` | 후속 조치 배열. 조치 문장 `action`, 관련 품목 코드 배열 `items`, 인용한 사실 번호 `findings` |
| `summary` | 가장 긴급한 내용부터 적은 요약 문자열 |

MeridianSeals 실행의 **AI 분석 응답 → 첫 번째 확인 질문**에 아래 객체가 들어 있습니다. C2는 이 객체의 `items`에서 `610001`과 `610002`를 읽고, 같은 공급처에 대해 전처리된 입력 품목 목록의 `item_code`에 두 값이 있는지 확인합니다. 이 목록의 코드는 재고 CSV의 `ItemCode` 열에서 가져옵니다. 두 코드 모두 있어 C2를 통과했습니다. C2의 대상은 분석 응답의 지정 코드 칸입니다. `figures_after_changes`의 코드와 값은 C10에서 다룹니다. [첫 번째 확인 질문](../dev/runs/2026-11-19_115421_walkthrough-sample-one-record-entry-per-agent/record.json#L336) · [C2 구현](../services/quality_checks.py#L215)

```json
{
  "question": "What expedited production, partial deliveries or faster shipping can you offer for BushingSleeve and GasketRing, and what are the earliest achievable delivery dates?",
  "ask": "supplier",
  "items": ["610001", "610002"],
  "findings": [1, 4, 5]
}
```

같은 응답에서 BushingSleeve의 변경 후 수치는 `{"item_code":"610001","new_lead_time_weeks":22,"new_risk_level":"Critical","new_gap_weeks":12,"new_latest_po_date":"2025-04-05"}`입니다. 코드는 품목별 조달 기간 제안을 적용해 재계산한 값으로 C6·C7·C10을 검사하고 Word 표를 구성합니다. 재고 수치를 인용한 분석 문장의 정확성은 J4로 확인합니다. [변경 후 수치 계산](../services/documents.py#L130) · [C6–C10 구현](../services/quality_checks.py#L319)

### 발주요청서의 입력과 응답

코드는 채택한 분석에서 발주 대상에 관련된 데이터를 고릅니다. `items`에는 품목·코드, 조달 기간, 위험도, 소진까지 남은 주수와 재고 공백, 권장 수량, 발주일·시급도·납기가 들어갑니다. `findings`는 대상과 사실 문장, 인용할 원문 문서 번호를 전달합니다. `changes`에는 기간 또는 수량의 변경 전후 값과 사유가, `actions`에는 관련 조치가 들어갑니다. 조달 기간 변경을 반영한 재고 수치와 수량 변경 제안은 각각 `items`와 `changes`에서 확인할 수 있습니다. [발주요청서 입력 조립](../services/documents.py#L531)

예를 들어 작성 모델의 `items`에 들어가는 BushingSleeve의 일부는 아래와 같습니다. 분석 입력의 재고 공백은 8주였고, 여기서는 변경된 22주 기준 12주가 들어갑니다.

```json
{
  "item_name": "BushingSleeve",
  "item_code": "610001",
  "risk_level": "Critical",
  "lead_time_weeks": 22,
  "expected_stockout_weeks": 12,
  "suggested_quantity": 1300,
  "order_by": "2025-04-05",
  "deliver_by": "2025-06-14"
}
```

응답 JSON의 `purpose`는 구매 목적을 1~2문장으로, `justification`은 사유를 2~4문장으로 담습니다. 모델은 근거가 된 문서 번호를 `[1]`처럼 표기합니다. 코드는 이 두 문단에서 인용 번호를 읽고 유효한 번호를 첫 등장 순서대로 매깁니다. Judge에는 작성 모델에 준 JSON과 두 문단을 함께 보내 사실·수치·의미가 어떻게 옮겨졌는지 확인합니다. [발주요청서 작성 프롬프트](../prompts/approval_request.md) · [인용 번호 처리](../services/documents.py#L575) · [발주요청서 Judge](../services/quality_checks.py#L733)

MeridianSeals 응답의 두 필드에서 첫 문장과 첫 인용까지 발췌하면 다음과 같습니다.

```json
{
  "purpose": "Approval is requested to purchase 1300 BushingSleeve, 2600 GasketRing, 2600 ValveCap and 2600 SealPlate from MeridianSeals.",
  "justification": "MeridianSeals announced that lead times for all products would increase by four weeks from 1 April 2025 during a moulding-line refit expected to last until the end of 2025 [1]"
}
```

### 이메일의 입력과 응답

이메일 작성 코드는 분석 JSON에서 `ask: "supplier"`로 표시된 질문 문장만 `points_to_clarify`로 옮깁니다. 주문 품목 정보는 이름·수량·요청 납기로 구성합니다. 재계산 후 Critical인 발주 대상 품목명은 `ask_earliest_dispatch`에, 같은 공급처에서 주문 대상 밖의 품목명은 `other_items`에 넣습니다. 재고량·재고 위험도·내부 질문을 담는 필드는 작성 입력에서 제외됩니다. 공급처용으로 표시된 질문 문장 안에 내부 표현이나 과거 문제 언급이 들어갈 수 있어, 작성 지시와 노출 검사를 함께 적용합니다. [이메일 입력 조립](../services/documents.py#L647)

```json
{
  "supplier": "MeridianSeals",
  "items": [
    {
      "item_name": "BushingSleeve",
      "quantity": 1300,
      "requested_delivery_date": "2025-06-14"
    }
  ],
  "points_to_clarify": [
    "What expedited production, partial deliveries or faster shipping can you offer for BushingSleeve and GasketRing, and what are the earliest achievable delivery dates?"
  ],
  "ask_earliest_dispatch": ["BushingSleeve", "GasketRing"],
  "other_items": ["OilRing"]
}
```

작성 프롬프트는 문의 문단만 `{"requests": "…"}`로 답하라고 지시합니다. 코드가 JSON에서 `requests`를 꺼냅니다. JSON 파싱에 실패하면 응답 원문을 문의 문장으로 보관하고 형식 문제를 기록합니다. 노출 검사기와 품질 Judge의 검사 대상도 이 문의 문장입니다. [이메일 작성 프롬프트](../prompts/email_draft.md) · [문의 문장 추출](../services/documents.py#L717)

MeridianSeals 실행의 첫 초안은 `moulding-line refit`과 `announced extension`을 언급했다는 사유로 노출 검사에서 실패했습니다. 그 사유를 작성 입력에 붙여 재작성한 두 번째 초안은 검사에 통과했습니다. 최종 응답은 통관 이력도 이번 주문의 수출 서류 확인 절차를 묻는 내용으로 바꿨습니다. [실행 기록의 `email_validation`과 `outputs.email_text`](../dev/runs/2026-11-19_115421_walkthrough-sample-one-record-entry-per-agent/record.json)

```json
{
  "requests": "Could you also outline the export-document checks for this order and confirm whether any outstanding documentation requirements could affect delivery?"
}
```

## 검사 모델이 받는 판정표와 응답 형식

세 Judge의 공통 `system` 지시는 **항목별로 근거를 먼저 쓰고, 통과 여부를 참·거짓으로 표시하고, 실패 시 구매 담당자용 메모를 한 문장으로 쓰라**는 것입니다. 검사별 `user` 메시지에는 작성 입력, 검사할 응답, 실제 적용하는 검사 문구를 넣습니다. 분석 Judge에는 기준 18주에서 계산한 원래 수치와 조건에 따라 코드로 재계산한 변경 후 수치를 별도 구획으로 보여줍니다. J3은 변경 방향·근거를, J4는 문장에 적힌 재고 수치가 해당 품목의 최종 값과 맞는지 봅니다. [공통 판정 지시와 분석 Judge 프롬프트](../services/quality_checks.py#L472)

다음은 **판정 응답의 형태를 보여주는 예시**입니다. E5는 이메일 품질 검사에서 질문 중복을 판정하는 항목입니다.

```json
{
  "E5": {
    "evidence": "The dispatch question appears twice.",
    "pass": false,
    "note": "The draft asks for the dispatch date twice."
  }
}
```

API에 보내는 스키마에서 검사 ID마다 `evidence`는 문자열이고 `pass`는 참·거짓입니다. 실패 메모 `note`는 문자열로 받을 수 있으며, 정리한 결과에는 실패 판정의 메모만 남깁니다. 검사 ID별 응답에서 판정이 누락되거나 코드가 끝까지 판정을 읽지 못하면 `pass: null`로 기록합니다. 최종 판정에서는 차단 항목이 `true`를 반환해야 통과입니다. [JSON 스키마](../services/quality_checks.py#L574) · [응답 읽기와 재시도](../services/quality_checks.py#L670) · [종합 판정](../services/quality_checks.py#L847)

이메일 **노출 검사기**에는 작성한 문의 문장과 주문 외 품목명을 입력합니다. 내부 정보, 과거 문제, 주문 외 품목 언급을 검사해 초안 한 건에 대해 `PASS` 또는 `FAIL: <사유>` 텍스트를 받습니다. 코드에서 특정 용어나 품목명을 먼저 찾은 경우, 그 사유가 바로 재작성에 들어갑니다. [노출 검사 프롬프트](../prompts/email_validator.md) · [검사 순서와 응답 해석](../services/agents.py#L514)

### Haiku 검증 실험에서 바뀐 API 요청과 응답

1차 실험 설정은 응답 형식 옵션을 생략했습니다. 그러자 Haiku 호출 코드의 기본 분기가 판정표를 받는 `record_verdicts` 도구의 인자 형식을 정의하고, `tool_choice`로 그 호출을 강제했습니다. 모델에는 여전히 `system` 규칙과 `user` 검증 텍스트가 들어갔습니다. API 응답의 `tool_use` 블록 안에 채점표가 들어왔고 Python이 그 블록의 `input`을 검사 결과로 읽었습니다. 아래는 응답에서 읽는 위치를 나타낸 예시입니다. [1차 실험 설정](../scripts/run_judge_validation.py#L45) · [Haiku API 어댑터](../services/quality_checks.py#L574)

```text
1차  API 응답 → tool_use → record_verdicts의 input → 검사 ID별 채점표
2차  API 응답 → text     → JSON 본문               → 검사 ID별 채점표
```

1차의 강제 호출 설정에서는 Haiku가 추론 단계를 건너뛰고 호출 요청부터 반환했습니다. 2차는 `output_config.format`으로 **답변 본문의 JSON 구조**를 지정했습니다. Haiku가 추론 후 채점표를 답변으로 반환하도록 하고, medium·high 추론 노력과 16,000토큰 출력 한도를 사용했습니다. 검출률 83.7%와 93.9%는 각각 1차와 2차 high의 실행 조건 전체에 대한 결과입니다. [실험 경위와 결과](judge_selection.md) · [Claude API의 강제 호출 동작](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#controlling-claudes-output)

## 검사 항목별 작성 지시와 확인 방법

표의 가운데 열은 해당 오류를 줄이기 위해 **작성 시점에 실제 적용되는 장치**입니다. 프롬프트로 요구하는 규칙과 코드가 입력을 구성하는 동작을 함께 적었습니다. 오른쪽 열은 실제 출력에서 확인하는 위치입니다. 검사마다 차단·검토 처리와 적용 조건은 [품질 기준표](eval_rubric.md)에 정리되어 있습니다.

### 구매 분석 코드 검사 C1–C10

| 검사 | 작성 시점에 적용한 장치 | 출력에서 확인하는 위치와 기준 |
|---|---|---|
| C1 · 출력 형식 | 분석 프롬프트에 필드 순서, 자료형, JSON 객체 예시를 제시하고 JSON만 요구 | 분석 응답을 파싱한 뒤 필수 최상위 필드의 형과 공급처 조달 기간 객체 또는 `null`을 확인 |
| C2 · 입력 품목 코드 | 입력에 품목명과 코드를 짝지어 제공. 사실·질문·조치·조달 기간 변경은 `items`, 수량 변경은 `item_code`에 관련 코드 기록. 공급처 전체 사항은 빈 배열 | 구조화된 응답의 해당 코드 값을 전처리 후 공급처별 입력 품목 목록과 대조 |
| C3 · 변경 전 주문량 | 수량 변경의 `original_quantity`는 입력 품목의 `suggested_quantity`를 그대로 옮기게 함 | `quantity_changes` 각 항목의 기존 수량과 동일 품목의 입력 권장 수량을 수치로 대조 |
| C4 · 근거 연결 | 문서에 번호·적용 범위를 부여하고, 각 사실에 문서 번호 또는 재고 근거를 기록. 변경·질문·조치에 적용되는 사실 번호를 적어도 하나 인용 | 사실 번호 중복과 인용 번호 존재, 문서 헤더 적용 범위, 판단과 인용 사실에 모두 품목 코드가 있을 때 코드가 겹치는지 확인 |
| C5 · 변경 구조와 산식 | 조달 기간을 주 단위로 쓰고, 품목당 최종 기간은 한 번만 지정. 공급처 공통 변경이 있으면 품목별 최종값을 제시. 수량은 원래 값×배율을 올림 | 기간의 수치·양수 여부와 품목 중복·누락을 확인. 수량 배율이 양수이고 1과 다른지, 제안 수량이 재계산한 값인지 대조 |
| C6 · Critical 대응 조치 | 변경 후 수치를 바탕으로 재고 공백을 적고, 모든 Critical 품목에 공백을 메울 조치를 제안. 조치에는 사실 번호를 부여 | 변경 반영 후 Critical 품목마다 해당 코드와 같은 품목의 재고 사실 번호가 함께 적힌 조치가 있는지 확인 |
| C7 · 요약의 Critical 품목 | 요약 첫 문장에 모든 Critical 품목명과 가장 긴 공백을 쓰게 함 | 코드가 재계산한 Critical 품목명을 대소문자·기호 등을 정규화해 `summary` 문자열에서 검색 |
| C8 · 요약 길이 | 긴급한 내용부터 약 100단어 내로 쓰고 품목별 상세와 조치 목록은 지정 필드에 작성 | `summary`를 공백으로 나눠 100단어 초과 여부 확인 |
| C9 · 변경 전후 표기 | 변경 수치는 제안 필드에 담고, 사유에 변경 전후 수치를 반복할 필요가 없다고 지시. 코드가 문서에 변경값을 표시 | 분석 본문의 화살표로 이은 숫자·날짜 쌍을 제안 필드에서 만든 조달 기간·수량 값의 쌍과 대조 |
| C10 · 변경 후 재계산 | 프롬프트에 위험도, 공백, 최종 발주일 산식 제시. 조달 기간 변경 대상마다 `figures_after_changes`에 계산값 요구 | 같은 품목의 조달 기간·위험도·공백·최종 발주일 네 값을 코드의 독립 재계산과 대조 |

근거. [분석 프롬프트](../prompts/analysis.md) · [C1–C10 구현](../services/quality_checks.py#L207) · [Word 조립과 수치 계산](../services/documents.py#L130)

### 구매 분석 Judge J1a–J8

| 검사 | 작성 시점에 적용한 장치 | Judge가 읽는 기준 |
|---|---|---|
| J1a · 원문에 있는 사실 | 이력 원문을 제공하고 확인 사실은 문서에서만 추출하며 출처 번호를 달게 함 | 분석이 말하는 과거 사건·추세·신뢰성의 근거가 제공된 원문에 있는지 확인 |
| J1b · 이력의 의미 보존 | 보고된 정도와 의미를 그대로 옮기도록 지시. 수요가 급증했다고 쓰인 경우 그 강도를 유지 | 서술을 원문과 대조해 과장·축소·변형이 있는지 확인 |
| J1c · 이력의 적용 범위 | 원문과 공급처·품목 헤더를 함께 제공. 공급처 공통 사실은 품목 코드 배열을 비우고 품목 이력은 문서가 지목한 코드에 연결 | 분석 문장이 원문에서 지목한 공급처·품목에 이력을 귀속했는지 확인 |
| J2a · 공급처 이슈 질문 | 공급처 전체에 적용되는 이력 문제에 대해 이번 주문에 어떤 영향이 있는지 묻도록 지시 | 발주에 영향을 주는 공급처 문제가 이력에 있으면 이를 다룬 확인 질문이 있는지 확인 |
| J2b · 품목 이슈 질문 | 주문 판단에 필요한 점을 질문으로 만들고 질문이 적용되는 품목 코드를 표기 | 해당 품목의 발주에 영향을 주는 이력 문제가 있으면 이를 다룬 질문이 있는지 확인 |
| J2c · 확인되지 않은 전제 | 근거가 있는 사실만 쓰고 변경·질문·조치마다 관련 사실 번호를 인용하도록 지시 | 질문이 입력에서 확인되지 않는 문제를 발생한 사실처럼 전제하는지 확인 |
| J3a · 변경 방향 | 조달 기간·수량 변화의 이유가 있는 경우에만 제안. 영국 외 시장 수요나 시장 불명 사례는 확인 질문 또는 공급 조건 확인으로 연결 | 인용한 사실이 제안한 증가·감소의 방향을 뒷받침하는지 확인 |
| J3b · 변경 폭 | 변경 폭의 이유를 기재하고, 수치가 없는 경우 문서 표현을 근거로 쓴 추정치와 확인 필요성을 표시. 공급처 공통 사유와 품목 사유의 합산·중복도 설명 | 제안 폭과 설명이 인용 사실에 비추어 맞는지 확인 |
| J3c · 변경 적용 대상 | 공급처 공통 기간이 바뀌면 품목마다 최종값을 쓰고 18주를 유지한 품목의 예외를 설명 | 같은 사유가 적용될 품목을 뺐거나 변경을 적용하지 않은 경우 그 예외의 근거 확인 |
| J4 · 문장에 인용한 재고 수치 | 변경 후 수치를 먼저 계산하고 이후 작성하는 문장은 그 수치를 사용. 변경이 없는 품목은 입력값을 그대로 사용 | 요약·사실 문장·질문·조치·변경 사유에 인용한 재고 수치·위험도·날짜를 코드가 계산한 최종 참고값과 대조 |
| J5 · 공급처 질문의 내부 정보 | 질문의 답할 주체를 `supplier` 또는 `internal`로 구분. 공급처 질문의 재고량·소진 기간·예산·자사 분석 공개를 금지 | `ask`가 `supplier`인 질문에서 내부 정보 노출 확인 |
| J6 · 질문과 조치의 근거 | 질문과 조치에 적용되는 사실 번호를 필수로 달게 함 | 인용 사실에서 그 질문이나 조치가 실제로 도출되는지 확인 |
| J7 · 중요한 이력의 미사용 | 의미 있는 이력 사실을 수집하고 주문 판단에 필요한 확인·변경·조치를 적게 함. 미사용 문서의 중요성은 Judge가 확인 | 어느 질문·변경·조치에도 근거로 연결되지 않은 문서 중 이번 발주에서 대응할 이슈가 있는지 확인 |
| J8 · 사실과 판단의 혼합 | `findings`에는 문서가 말한 사실을, `stock_findings`에는 재고상의 사실을 쓰게 함. 해석은 질문·변경·조치 필드에 둠 | 사실 필드에 이번 발주에 대한 판단이 섞였는지 확인 |

운영에서 J2a는 공급처가 명시된 문서, J2b는 품목이 명시된 문서가 있을 때 판정 목록에 넣고 Judge가 해당 문제의 중요성을 판단합니다. 모델 평가에서 중요 문제가 있는지 라벨을 제공한 경우, 라벨로 J2a·J2b 적용 여부를 결정합니다. J3·J5·J6·J7·J8도 각각 변경, 공급처 질문, 질문·조치, 미사용 문서, 확인 사실의 존재에 따라 적용합니다. [판정 적용 조건](../services/quality_checks.py#L417) · [판정 기준 원문](../services/quality_checks.py#L85)

### 발주요청서 검사 P1a–P3

| 검사 | 작성 시점에 적용한 장치 | 출력에서 확인하는 위치와 기준 |
|---|---|---|
| P1a · 새 사실·평가 | 관련 수치·확인 사실·변경·조치만 입력하고, 입력에 없는 위험·공급처 평가를 추가하지 않도록 지시. 발주 전 확인 사항은 결재의 조건으로 기술 | Judge가 목적·사유를 작성 입력과 대조해 새 사실·위험·평가를 확인 |
| P1b · 수치 보존 | 코드가 계산한 수치를 제공. 그대로 옮기고 자체 계산이나 빠르다·느리다 같은 평가를 붙이지 말라고 지시 | Judge가 두 문단의 수치와 수식어를 입력값과 대조 |
| P1c · 의미 보존 | 근거가 말하는 범위에서만 표현하라고 지시. 예를 들어 대략적인 값은 그 정도를 유지 | Judge가 바꿔 쓴 표현이 원래 의미나 확실성을 바꿨는지 확인 |
| P2 · 문장 수 | `purpose` 1~2문장, `justification` 2~4문장으로 JSON 구조에 명시 | 코드가 마침표·물음표·느낌표 뒤에 공백과 영문 대문자가 오는 위치를 기준으로 두 값을 나눠 문장 수를 확인 |
| P3 · 인용 번호 | 각 확인 사실에 원문 번호를 제공하고 그 번호만 대괄호로 쓰도록 지시. 재고 수치에는 출처 번호를 붙이지 않도록 지시 | 코드가 두 문단에서 숫자 인용 표기를 추출해 제공된 이력 문서 번호 범위를 확인 |

근거. [발주요청서 프롬프트](../prompts/approval_request.md) · [P1a–P3 검사](../services/quality_checks.py#L716) · [P3 인용 처리](../services/documents.py#L575)

### 공급처 이메일 검사 E1–E7

| 검사 | 작성 시점에 적용한 장치 | 출력에서 확인하는 위치와 기준 |
|---|---|---|
| E1 · 내부 정보 | 코드가 품목별 이름·수량·납기와 공급처용 질문을 전달. 작성 프롬프트에 재고·위험도·내부 검토·도구 언급 금지. 재작성 시 내부 정보 보호 지시를 추가 | 코드가 문의 문장에서 내부 용어를 검색하고, 노출 검사 모델이 재고·소진 주수·위험 평가 및 내부 분석·검토·로직·도구 언급을 확인 |
| E2 · 과거 문제 | 작성 프롬프트에 과거 이슈의 사건명과 시점을 빼고 이번 주문의 관련 절차나 확인 방법을 묻도록 지시 | 노출 검사 모델이 문의 문장에서 과거 문제와 시점의 언급 여부를 확인 |
| E3 · 주문 외 품목 | `items`로 주문 품목을, `other_items`로 주문 외 품목명을 제공. 확인할 사항에 있더라도 주문 외 품목을 빼도록 지시 | 코드가 주문 외 품목명·코드를 검색하고 노출 검사 모델이 우회 표현을 확인 |
| E4 · 확인 사항 누락 | 분석의 공급처용 질문을 `points_to_clarify`로 건네고 필요한 정보를 얻는 질문으로 바꾸게 함. 과거 이슈는 이번 주문의 절차를 묻도록 지시 | Judge가 해당 목록과 문의 문장을 대조. 이번 주문에 필요한 내용의 누락과 주문 외 품목 질문을 확인 |
| E5 · 질문 중복 | 같은 정보를 구하는 질문을 합치고 제출 전 중복을 점검하도록 지시 | Judge가 문의 문단에서 같은 질문이 반복되는지 확인 |
| E6 · 조기 출하 문의 | 조기 출하를 물을 품목을 `ask_earliest_dispatch`에 따로 제공. 품목마다 가장 빠른 출하일을 묻되 그 품목의 조기 출하나 납품을 이미 묻는 질문이 있으면 활용하도록 지시 | Judge가 목록의 품목마다 가장 빠른 출하일이나 표준 기간보다 빠른 납품을 묻는 요청이 있는지 확인 |
| E7 · 이메일 문체와 확약 | 품목 목록은 코드가 상단에 배치. 문의 문단은 이미 표시된 품목을 가리키고 문장으로 정중히 요청하며 발주를 약속하지 않도록 지시 | Judge가 품목 목록 반복, 발주 확약, 내부 메모나 질문 나열처럼 읽히는지 확인 |

근거. [이메일 작성 프롬프트](../prompts/email_draft.md) · [노출 검사 E1–E3](../services/agents.py#L514) · [이메일 품질 Judge E4–E7](../services/quality_checks.py#L770)

## 실패 사유가 다음 단계로 가는 위치

| 결과 | 다음 동작 |
|---|---|
| 분석의 차단 항목 실패 | 실패 항목과 사유를 보내 전체 분석을 재작성합니다. 기본 최대 2회입니다. 코드 차단 검사에 실패하고 재작성 기회가 있으면 곧바로 재작성합니다. 기회를 모두 사용하면 차단 실패가 가장 적은 응답을 사용하고, 이전 응답을 채택한 경우 다시 검사합니다. |
| 분석의 검토 항목 또는 발주요청서 검사 실패 | 남은 문제를 Word 검토 메모와 품질 평가보고서에 표시합니다. |
| 이메일 노출 검사 실패 | 사유를 작성 입력에 붙여 문의 문장을 재작성합니다. 최대 2회 재작성하며, 이후에도 실패하면 마지막 초안에 해당 사유를 표시합니다. |
| 이메일 품질 Judge의 검토 항목 | 마지막 문의 문장의 문제를 초안 상단 메모에 표시합니다. |

프로덕션 실행 기록에는 원본 CSV, 공급처별 품목 데이터와 사용한 이력, 모델 설정, 프롬프트 해시, 분석·문서 출력과 검사 결과가 남습니다. 개발 사례의 실행 기록에는 고정 프롬프트 원문도 있습니다. 각 예시의 결과를 확인할 때 구매 분석은 `outputs.analysis`, 문서 작성 결과는 `outputs.approval` 및 `outputs.email_text`, 검사는 `evaluation`·`approval_check`·`email_validation`·`email_check`를 보면 됩니다. [분석 재작성 제어](../services/agents.py#L382) · [최종 검토 메모](../services/agents.py#L470) · [실행 기록 필드](../services/run_record.py#L103) · [개발 사례 안내](../dev/README.md)
