import asyncio
import json
import os
import sys

from dotenv import load_dotenv
from groq import AsyncGroq

# Pour pouvoir importer agent.py
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from agent import run_agent

load_dotenv()
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
EVAL_MODEL = "llama-3.3-70b-versatile"

client = AsyncGroq(api_key=GROQ_API_KEY)


async def get_bot_response(question: str, session_id: str) -> str:
    response = ""
    # Consomme le generateur asynchrone
    async for chunk in run_agent(question, session_id):
        pass # The yield chunks are partial, we only care about the full response which is built inside or we can just accumulate chunks
        # Actually in run_agent:
        # yield to_send
    
    # Let's fix that. In agent.py, run_agent yields partial strings. We can accumulate them.
    # Wait, the way run_agent works is: it yields chunks.
    # So we just accumulate them.
    response = ""
    async for val in run_agent(question, session_id):
        response += val
    return response


async def evaluate_response(question: str, expected_topics: list[str], bot_answer: str) -> dict:
    prompt = f"""Tu es un évaluateur expert de chatbot RAG.
Tu dois évaluer la réponse d'un chatbot selon 2 critères (sur 5).

Question posée au bot : "{question}"
Réponse fournie par le bot : "{bot_answer}"
Sujets/mots-clés attendus (Ground Truth) : {', '.join(expected_topics)}

Critères :
1. Pertinence (Relevance) : 1 à 5. Le bot a-t-il répondu exactement à la question sans digression ? (5 = parfait, 1 = hors sujet total)
2. Fidélité et Rappel (Faithfulness/Recall) : 1 à 5. Le bot a-t-il mentionné les informations attendues sans inventer de fausses infos (hallucination) ?

Réponds STRICTEMENT sous forme de JSON valide avec les clés "relevance", "faithfulness", et "reason" (une courte explication d'une phrase).
"""
    try:
        completion = await client.chat.completions.create(
            model=EVAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Erreur d'évaluation pour la question '{question}': {e}")
        return {"relevance": 0, "faithfulness": 0, "reason": str(e)}


async def main():
    print("Demarrage de l'evaluation RAG (LLM-as-a-Judge)")
    dataset_path = os.path.join(os.path.dirname(__file__), 'golden_dataset.json')
    
    with open(dataset_path, 'r', encoding='utf-8') as f:
        dataset = json.load(f)
        
    total_relevance = 0
    total_faithfulness = 0
    
    for i, item in enumerate(dataset):
        q = item["question"]
        expected = item["expected_topics"]
        
        print(f"\n[{i+1}/{len(dataset)}] Q: {q}")
        bot_response = await get_bot_response(q, f"eval_session_{i}")
        # print(f"  Bot: {bot_response}")
        
        eval_result = await evaluate_response(q, expected, bot_response)
        rel = eval_result.get("relevance", 0)
        faith = eval_result.get("faithfulness", 0)
        reason = eval_result.get("reason", "")
        
        print(f"  --> Rel: {rel}/5 | Faith: {faith}/5")
        print(f"  --> {reason}")
        
        total_relevance += rel
        total_faithfulness += faith
        
    avg_rel = total_relevance / len(dataset)
    avg_faith = total_faithfulness / len(dataset)
    
    print("\n" + "="*40)
    print("RESULTATS GLOBAUX")
    print(f"Pertinence moyenne : {avg_rel:.2f} / 5")
    print(f"Fidélité moyenne   : {avg_faith:.2f} / 5")
    print("="*40)


if __name__ == "__main__":
    asyncio.run(main())
