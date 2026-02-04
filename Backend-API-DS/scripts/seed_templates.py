"""
Seed script to populate templates table with default discharge summary templates.
"""
import asyncio
import sys
from pathlib import Path

# Add project path
root_dir = Path(__file__).parent.parent.parent
backend_dir = root_dir / "Backend-API-DS"
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(backend_dir))

from app.db.session import AsyncSessionLocal
from app.db.models.template import Template


TEMPLATES = [
    {
        "template_id": "standard",
        "name": "Standard Discharge Summary",
        "description": "Comprehensive template for general medical cases",
        "template_type": "standard",
        "category": "General",
        "estimated_time": 5,
        "sections": [
            "Patient demographics, admission/discharge dates, diagnoses, medications, follow up instructions..."
        ],
    },
    {
        "template_id": "cardiac",
        "name": "Cardiac Discharge Summary",
        "description": "Specialized template for cardiac procedures and conditions",
        "template_type": "detailed",
        "category": "Cardiology",
        "estimated_time": 8,
        "sections": [
            "Cardiac-specific assessments, procedures, medications, rehabilitation recommendations..."
        ],
    },
    {
        "template_id": "surgical",
        "name": "Surgical Discharge Summary",
        "description": "Template for post-surgical patients",
        "template_type": "detailed",
        "category": "Surgery",
        "estimated_time": 7,
        "sections": [
            "Surgical procedure details, post-op course, wound care, activity restrictions..."
        ],
    },
    {
        "template_id": "pediatric",
        "name": "Pediatric Discharge Summary",
        "description": "Child-specific template with growth parameters",
        "template_type": "standard",
        "category": "Pediatrics",
        "estimated_time": 6,
        "sections": [
            "Age-appropriate assessments, growth charts, parent education, vaccination status..."
        ],
    },
    {
        "template_id": "mental-health",
        "name": "Mental Health Discharge Summary",
        "description": "Template for psychiatric and mental health cases",
        "template_type": "detailed",
        "category": "Psychiatry",
        "estimated_time": 9,
        "sections": [
            "Mental status exam, medication management, safety plan, therapy recommendations..."
        ],
    },
    {
        "template_id": "emergency",
        "name": "Emergency Department Summary",
        "description": "Quick template for ED discharges",
        "template_type": "brief",
        "category": "Emergency",
        "estimated_time": 4,
        "sections": [
            "Chief complaint, ED course, disposition, return precautions..."
        ],
    },
]


async def seed_templates():
    """Seed templates into the database."""
    from sqlalchemy import select, func
    
    async with AsyncSessionLocal() as session:
        # Check if templates already exist
        result = await session.execute(select(func.count()).select_from(Template))
        existing_count = result.scalar()
        
        if existing_count > 0:
            print(f"⚠️  Templates already exist ({existing_count} templates found).")
            overwrite = input("Do you want to overwrite? (yes/no): ")
            if overwrite.lower() != "yes":
                print("❌ Seeding cancelled.")
                return
            
            # Delete existing templates
            result = await session.execute(select(Template))
            templates = result.scalars().all()
            for t in templates:
                await session.delete(t)
            await session.commit()
            print("🗑️  Deleted existing templates.")
        
        # Insert new templates
        for template_data in TEMPLATES:
            template = Template(**template_data, is_active=True)
            session.add(template)
        
        await session.commit()
        print(f"✅ Successfully seeded {len(TEMPLATES)} templates!")
        
        # Display seeded templates
        print("\n📋 Seeded Templates:")
        for t in TEMPLATES:
            print(f"  - {t['name']} ({t['category']}) - {t['template_type']}")


if __name__ == "__main__":
    print("🌱 Starting template seeding...")
    asyncio.run(seed_templates())
