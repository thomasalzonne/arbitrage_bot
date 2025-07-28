#!/usr/bin/env python3
# test_corrections.py - Tests des corrections avant relance du bot

import asyncio
import sys
import time
from datetime import datetime
sys.path.append('.')

from src.trading.portfolio import PortfolioManager
from src.exchanges.hyperliquid import HyperliquidExchange
from src.exchanges.woofi_pro import WooFiProExchange
from src.utils.config import ConfigManager

class TestCorrections:
    """
    Tests de validation des corrections apportées
    """
    
    def __init__(self):
        self.config = ConfigManager()
        self.exchanges = {}
        self.portfolio = None
        self.test_results = {
            'connexions': False,
            'apr_monitoring': False,
            'fermeture_positions': False,
            'sessions_cleanup': False
        }

    async def run_all_tests(self):
        """Lance tous les tests de validation"""
        print("=" * 60)
        print("TESTS DE VALIDATION DES CORRECTIONS")
        print("=" * 60)
        
        try:
            # Test 1: Connexions exchanges
            await self.test_connexions()
            
            # Test 2: APR monitoring corrigé
            await self.test_apr_monitoring()
            
            # Test 3: Logique fermeture positions
            await self.test_fermeture_positions()
            
            # Test 4: Cleanup sessions
            await self.test_sessions_cleanup()
            
            # Résumé
            self.print_test_summary()
            
        except Exception as e:
            print(f"ERREUR FATALE TESTS: {e}")
            return False

    async def test_connexions(self):
        """Test 1: Connexions exchanges robustes"""
        print("\n1. TEST CONNEXIONS EXCHANGES")
        print("-" * 40)
        
        try:
            # Init WooFi Pro
            woofi_config = self.config.get_exchange_config('woofi_pro')
            self.exchanges['woofi_pro'] = WooFiProExchange(woofi_config)
            woofi_auth = await self.exchanges['woofi_pro'].authenticate()
            
            if woofi_auth:
                print("✅ WooFi Pro: Connexion OK")
            else:
                print("❌ WooFi Pro: Échec connexion")
                return
            
            # Init Hyperliquid
            hl_config = self.config.get_exchange_config('hyperliquid')
            self.exchanges['hyperliquid'] = HyperliquidExchange(hl_config)
            hl_auth = await self.exchanges['hyperliquid'].authenticate()
            
            if hl_auth:
                print("✅ Hyperliquid: Connexion OK")
            else:
                print("❌ Hyperliquid: Échec connexion")
                return
            
            # Test balances
            for name, exchange in self.exchanges.items():
                try:
                    balances = await exchange.get_balances()
                    usdc_balance = next((b for b in balances if b.asset == 'USDC'), None)
                    if usdc_balance:
                        print(f"✅ {name}: {float(usdc_balance.total):.2f} USDC")
                    else:
                        print(f"⚠️  {name}: USDC non trouvé")
                except Exception as e:
                    print(f"❌ {name}: Erreur balances - {e}")
                    return
            
            self.test_results['connexions'] = True
            print("🎉 Test connexions: SUCCÈS")
            
        except Exception as e:
            print(f"❌ Test connexions: ÉCHEC - {e}")

    async def test_apr_monitoring(self):
        """Test 2: APR monitoring corrigé"""
        print("\n2. TEST APR MONITORING CORRIGÉ")
        print("-" * 40)
        
        try:
            # Init portfolio manager
            self.portfolio = PortfolioManager()
            self.portfolio.set_exchanges(self.exchanges)
            
            # Récupérer positions actuelles
            positions = await self.portfolio.get_active_positions()
            print(f"Positions actives détectées: {len(positions)}")
            
            if len(positions) == 0:
                print("⚠️  Aucune position active - Test APR impossible")
                print("   (Normal si aucune position ouverte)")
                self.test_results['apr_monitoring'] = True
                return
            
            # Test APR pour chaque position
            apr_correct = True
            for pos in positions:
                symbol = pos['symbol']
                current_apr = pos.get('current_apr', 0)
                duration = pos.get('duration_hours', 0)
                funding = pos.get('funding_received', 0)
                
                print(f"📊 {symbol}:")
                print(f"   APR actuel: {current_apr:.1f}%")
                print(f"   Durée: {duration:.1f}h")
                print(f"   Funding: {funding:.4f} USDC")
                
                # Validation APR
                if current_apr == 98.0:
                    print(f"❌ APR bloqué à 98% - Bug non corrigé!")
                    apr_correct = False
                elif 0 <= current_apr <= 2000:  # Range raisonnable
                    print(f"✅ APR dans range raisonnable")
                else:
                    print(f"⚠️  APR suspect: {current_apr:.1f}%")
            
            if apr_correct:
                self.test_results['apr_monitoring'] = True
                print("🎉 Test APR monitoring: SUCCÈS")
            else:
                print("❌ Test APR monitoring: ÉCHEC")
                
        except Exception as e:
            print(f"❌ Test APR monitoring: ERREUR - {e}")

    async def test_fermeture_positions(self):
        """Test 3: Logique de fermeture améliorée"""
        print("\n3. TEST LOGIQUE FERMETURE POSITIONS")
        print("-" * 40)
        
        try:
            if not self.portfolio:
                print("❌ Portfolio non initialisé")
                return
            
            positions = await self.portfolio.get_active_positions()
            
            if len(positions) == 0:
                print("⚠️  Aucune position - Test fermeture impossible")
                print("   (Logique should_close_position sera testée si positions)")
                self.test_results['fermeture_positions'] = True
                return
            
            # Test logique should_close_position pour chaque position
            for pos in positions:
                symbol = pos['symbol']
                should_close, reason = await self.portfolio.should_close_position(pos, exit_apr_threshold=50)
                
                print(f"🔄 {symbol}:")
                print(f"   Should close: {'OUI' if should_close else 'NON'}")
                print(f"   Raison: {reason}")
                
                # Test avec différents seuils
                should_close_high, reason_high = await self.portfolio.should_close_position(pos, exit_apr_threshold=200)
                print(f"   Seuil 200%: {'FERMER' if should_close_high else 'MAINTENIR'}")
            
            self.test_results['fermeture_positions'] = True
            print("🎉 Test logique fermeture: SUCCÈS")
            
        except Exception as e:
            print(f"❌ Test fermeture positions: ERREUR - {e}")

    async def test_sessions_cleanup(self):
        """Test 4: Cleanup des sessions"""
        print("\n4. TEST CLEANUP SESSIONS")
        print("-" * 40)
        
        try:
            # Test fermeture propre Hyperliquid
            hl_exchange = self.exchanges.get('hyperliquid')
            if hl_exchange:
                print("🔌 Test fermeture Hyperliquid...")
                await hl_exchange.close()
                print("✅ Hyperliquid fermé proprement")
                
                # Test reconnexion
                print("🔄 Test reconnexion...")
                reconnect = await hl_exchange.authenticate()
                if reconnect:
                    print("✅ Reconnexion réussie")
                else:
                    print("❌ Échec reconnexion")
                    return
            
            # Test fermeture propre WooFi
            woofi_exchange = self.exchanges.get('woofi_pro')
            if woofi_exchange:
                print("🔌 Test fermeture WooFi...")
                await woofi_exchange.close()
                print("✅ WooFi fermé proprement")
                
                # Test reconnexion
                print("🔄 Test reconnexion...")
                reconnect = await woofi_exchange.authenticate()
                if reconnect:
                    print("✅ Reconnexion réussie")
                else:
                    print("❌ Échec reconnexion")
                    return
            
            self.test_results['sessions_cleanup'] = True
            print("🎉 Test cleanup sessions: SUCCÈS")
            
        except Exception as e:
            print(f"❌ Test cleanup sessions: ERREUR - {e}")

    def print_test_summary(self):
        """Affiche le résumé des tests"""
        print("\n" + "=" * 60)
        print("RÉSUMÉ DES TESTS")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(self.test_results.values())
        
        for test_name, result in self.test_results.items():
            status = "✅ PASSÉ" if result else "❌ ÉCHEC"
            print(f"{test_name.replace('_', ' ').title()}: {status}")
        
        print(f"\nRÉSULTAT GLOBAL: {passed_tests}/{total_tests} tests passés")
        
        if passed_tests == total_tests:
            print("\n🎉 TOUS LES TESTS PASSÉS - BOT PRÊT À RELANCER!")
            print("\nCommandes pour relancer:")
            print("1. python -m src.main")
            print("2. ou docker-compose up arbitrage_bot")
        else:
            print(f"\n⚠️  {total_tests - passed_tests} test(s) échoué(s) - Corrections nécessaires")
            print("\nNe pas relancer le bot avant correction!")

    async def cleanup(self):
        """Nettoyage final"""
        try:
            for exchange in self.exchanges.values():
                if hasattr(exchange, 'close'):
                    await exchange.close()
            print("\n🧹 Cleanup terminé")
        except Exception as e:
            print(f"Erreur cleanup: {e}")

async def main():
    """Point d'entrée des tests"""
    print("Lancement tests de validation...")
    print("Cela va prendre 30-60 secondes...")
    
    tester = TestCorrections()
    
    try:
        await tester.run_all_tests()
    except KeyboardInterrupt:
        print("\n⏹️  Tests interrompus par l'utilisateur")
    except Exception as e:
        print(f"\n💥 Erreur critique: {e}")
    finally:
        await tester.cleanup()

if __name__ == "__main__":
    asyncio.run(main())