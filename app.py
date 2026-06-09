import os
import json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from parse import parse_jewelry_data
from deparse import parse_to_json_structure
import jew_lm

app = FastAPI(title="Jewelry AI Service", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    action: str
    formData: dict
    images: List[str]

class AnalyzeResponse(BaseModel):
    success: bool
    result: dict
    error: Optional[str] = None

@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_jewelry(request: AnalyzeRequest):
    try:
        json_string = json.dumps({
            "action": request.action,
            "formData": request.formData,
            "images": request.images
        }, ensure_ascii=False)

        result_string, images_data = parse_jewelry_data(json_string)

        print(f"Result string: {result_string}")
        print(f"Images count: {len(images_data)}")

        verified_context, dimensions = jew_lm.integrate_verification_report(result_string, images_data)

        formData = request.formData.copy()
        calculated_weight = None

        if dimensions.get('outer_diameter_mm') and dimensions.get('inner_diameter_mm'):
            purity = int(formData.get('purity', 585))
            height = dimensions.get('height_mm', 2.5)
            calculated_weight = jew_lm.calculate_weight_from_dimensions(
                dimensions['outer_diameter_mm'],
                dimensions['inner_diameter_mm'],
                height,
                purity
            )
            print(f"Calculated weight from dimensions: {calculated_weight} g")

            if not formData.get('weight'):
                formData['weight'] = str(calculated_weight)

        # Пересобираем строку параметров с обновлённым весом
        updated_result_string = f"{formData.get('type', '')};{formData.get('purity', '')};{formData.get('hasStones', '')};{formData.get('condition', '')};{formData.get('weight', '')}"

        verified_context_updated, _ = jew_lm.integrate_verification_report(updated_result_string, images_data)

        response = jew_lm.run_agent(verified_context_updated)
        correct_json = parse_to_json_structure(response, none_as_string=False)
        result = json.loads(correct_json)["result"]

        if calculated_weight and not request.formData.get('weight'):
            result['calculated_weight'] = calculated_weight

        return {
            "success": True,
            "result": result
        }

    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            "success": False,
            "result": {},
            "error": str(e)
        }

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "jewelry-ai"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5001)