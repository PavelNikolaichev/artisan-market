"""Generate random purchase history."""
import os.path
import random
import pandas as pd

from src.utils.data_parser import DataParser


class PurchaseGenerator:
    def __init__(self):
        self.parser = DataParser()
        self.users = self.parser.parse_users()
        self.products = self.parser.parse_products()

    def generate_purchases(self, num_purchases: int = 75) -> pd.DataFrame:
        """Generate random purchases based on user interests."""
        purchases = []
        
        # Well, it wasn't me who came up with one-by-one purchases. So I will generate purchases one by one.
        for i in range(num_purchases):
            # Consider:
            # - User interests matching product tags [check]
            # - Seasonal patterns
            # - Price ranges [kinda check, considering product amounts and stock]
            # - User join date constraints [check]
            user = self.users.sample().iloc[0]
            user_preferences = user["interests"]

            # Let's try to match products with user interests
            matching_products = self.products[
                self.products["tags"].apply(lambda tags: any(tag in user_preferences for tag in tags))
            ]

            product = self.products.sample().iloc[0] \
                if matching_products.empty\
                else matching_products.sample().iloc[0]
            
            # Purchase date is a random date after the user's join date until today
            purchase_date = user['join_date']    
            purchase_date += pd.Timedelta(days=random.randint(0, (pd.Timestamp.now() - user['join_date']).days))
            
            purchase = {
                "user_id": user["ID"],
                "product_id": product["ID"],
                # Note that several users may purchase more than available stock - cope with it.
                "quantity": min(random.randint(1, 5), product['STOCK']),  # Random quantity, capped by stock
                "date": purchase_date,
            }
            
            purchases.append(purchase)

        return pd.DataFrame(purchases)

    def save_purchases(self, purchases: pd.DataFrame, filename: str = "purchases.csv"):
        """Save generated purchases to CSV. Note, there's no check for existing file or path."""
        purchases.to_csv(os.path.join(".", "raw_data", filename), index=False)
        print(f"Purchases saved to {filename}")


if __name__ == "__main__":
    generator = PurchaseGenerator()
    purchases = generator.generate_purchases()
    generator.save_purchases(purchases)
    print(f"Generated {len(purchases)} purchases")
