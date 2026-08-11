import logging
import database

logger = logging.getLogger(__name__)

SCIENTIFIC_WORD_BANK = [
    "Zynthera", "Vexarion", "Astronyx", "Kyroven", "Xytheron", "Nexvion", "Zerovex", "Aetherix",
    "Vortexion", "Cryvanta", "Zynovex", "Axionyx", "Veltrion", "Xenovra", "Nexarion", "Zorvex",
    "Astravex", "Kyronix", "Vexoria", "Zenthrox", "Xyronis", "Nevarix", "Astrixor", "Voltraxis",
    "Zyphor", "Nexora", "Vantorix", "Xevrion", "Zorathix", "Kyvex", "Aetheron", "Vextron",
    "Zyntrix", "Xandryx", "Novarix", "Cryonex", "Vortyra", "Zyronix", "Nexthar", "Axevion",
    "Astryx", "Veltrax", "Xynovex", "Zorvian", "Kytherix", "Vexalor", "Nexyron", "Zenthrix",
    "Xyvaron", "Auronex", "Voidrix", "Starvex", "Cyberion", "Quantyx", "Neurovex", "Techryon",
    "Galaxion", "Cosmoryx", "Quantumix", "Cybervanta", "Nexquant", "Astronex", "Voidara",
    "Stellaryx", "Chronovex", "Darknex", "Omnixor", "Hyperionyx", "Cyberyx", "Technovra",
    "Galaxor", "Neonvex", "Quantumra", "Cosmion", "Voidvanta", "Staronyx", "Chronyx", "Nexvoid",
    "Hypervex", "Zyphron", "Xenoryx", "Vortyron", "Astravon", "Nexzora", "Zorvexis", "Kyronova",
    "Vexyron", "Xythera", "Zynova", "Auronix", "Velzora", "NexoraX", "Voidrion", "AstronyxX",
    "Xevora", "Zenthora", "Vantyx", "Omnithor", "Zyverion", "QuantumForge", "PhotonX",
    "Neutronix", "PlasmaCore", "Orbitron", "NexPhoton", "QuantumVex", "CosmoNex", "AetherCore",
    "NovaFlux", "SingularX", "DarkMatterX", "ChronoCore", "NeuroNex", "CyberPhoton", "QuantumNova",
    "PlasmaNex", "OrbitXen", "PhotonForge", "AstroVex", "NeutronCore", "QuantumDrift",
    "CosmicNexus", "NovaCircuit", "AxiomX", "EntropyX", "IonVortex", "PhotonNexus", "PlasmaVortex",
    "QuantumDriftX", "HyperNova", "AstroCore", "DarkNova", "VoidMatter", "ChronoFlux",
    "NeuroFlux", "IonForge", "QuantumPulse", "PhotonPulse", "CosmoFlux", "GravityX",
    "GravityNex", "OrbitalX", "SolarNexus", "LunarCore", "StellarX", "StellarForge", "NebulaX",
    "NebulaCore", "GalacticNex", "ExoNexus", "ExoForge", "AstroNex", "AstroFlux", "CosmoForge",
    "CosmoXen", "QuantumArc", "QuantumVoid", "QuantumRift", "QuantumRealm", "SingularityX",
    "EventHorizonX", "HorizonNex", "VoidHorizon", "DarkEnergyX", "DarkPhoton", "DarkOrbit",
    "MatterNex", "AntimatterX", "AntimatterNex", "NeonPhoton", "NeonQuantum", "NeonOrbit",
    "NeonNexus", "CyberNova", "CyberOrbit", "CyberNexus", "TechnoNova", "TechnoQuantum",
    "TechnoFlux", "AxiomForge", "AxiomNexus", "AxiomNova", "NexusPrime", "NexusVoid",
    "NexusOrbit", "NexusFlux", "NexusCore", "NexusPhoton", "NexusQuantum", "ZeroPointX",
    "ZeroGravityX", "InfiniteNex", "InfinityCore", "InfinityFlux", "TimeWarpX", "SpaceNexus",
    "SpaceForge", "RealityX", "RealityNex", "Catalyst", "Isotope", "Vector", "Scalar",
    "Spectrum", "Photon", "Electron", "Proton", "Neutrino", "Muon", "Boson", "Fermion",
    "Quark", "Gluon", "Lepton", "Hadron", "Meson", "Baryon", "Positron", "Graviton",
    "Magnetism", "Induction", "Resonance", "Refraction", "Diffraction", "Interference",
    "Polarization", "Radiance", "Luminosity", "Wavelength", "Amplitude", "Frequency",
    "Momentum", "Inertia", "Velocity", "Acceleration", "Kinetics", "Dynamics", "Turbulence",
    "Oscillation", "Entropy", "Enthalpy", "Catalysis", "Reagent", "Solvent", "Solute",
    "Molecule", "Compound", "Element", "Polymer", "Crystal", "Alloy", "Oxide", "Hydride",
    "Isomer", "Polymerase", "Solubility", "Volatility", "Equilibrium", "Atom", "Nucleus",
    "Orbit", "Eclipse", "Comet", "Asteroid", "Meteorite", "Pulsar", "Quasar", "Galaxy",
    "Exoplanet", "Protostar", "Supernova", "Magnetar", "Nebula", "Aphelion", "Perihelion",
    "Zenith", "Nadir", "Equinox", "Algorithm", "Matrix", "Tensor", "Fractal", "Topology",
    "Symmetry", "Probability", "Variable", "Constant", "Derivative", "Integral", "Convergence",
    "Divergence", "Continuum", "Dimension", "Invariant", "Covalent", "Valence", "Affinity"
]

class ReferralManager:
    @staticmethod
    def get_verified_referrals_count(user_id: int) -> int:
        return database.get_verified_referrals_count(user_id)

    @staticmethod
    def get_or_create_user_ref_code(user_id: int) -> str:
        user = database.get_user(user_id)
        if user and user.get("ref_code"):
            return user["ref_code"]
            
        # Pick from scientific word bank deterministically or based on user_id offset
        word_index = (user_id % len(SCIENTIFIC_WORD_BANK))
        base_word = SCIENTIFIC_WORD_BANK[word_index]
        candidate = base_word
        
        # Check if candidate is taken; if so, append suffixes (_X, _2, _3)
        attempt = 1
        while database.get_user_by_ref_code(candidate):
            if attempt == 1:
                candidate = f"{base_word}X"
            else:
                candidate = f"{base_word}_{attempt}"
            attempt += 1
            
        database.set_user_ref_code(user_id, candidate)
        return candidate

    @staticmethod
    def resolve_referrer_id(ref_arg: str) -> int:
        if not ref_arg:
            return None
        clean_arg = ref_arg.replace("ref_", "").strip()
        if clean_arg.isdigit():
            return int(clean_arg)
        user = database.get_user_by_ref_code(clean_arg)
        return user["user_id"] if user else None

    @staticmethod
    def calculate_referral_reward_amount(referred_user_id: int) -> int:
        from datetime import datetime, timezone
        user = database.get_user(referred_user_id)
        if not user or not user.get("created_at"):
            return 3
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        created_dt = user["created_at"]
        if isinstance(created_dt, str):
            try:
                created_dt = datetime.fromisoformat(created_dt)
            except Exception:
                return 3
        if created_dt and created_dt.tzinfo is not None:
            created_dt = created_dt.replace(tzinfo=None)
            
        diff_sec = (now - created_dt).total_seconds()
        # 24-Hour Flash Power-Hour Boost: 5 Credits if joined within 24h
        return 5 if diff_sec <= 86400 else 3

    @staticmethod
    def register_referral(referred_user_id: int, inviter_user_id: int):
        conn = database.get_db_connection()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO referrals (referred_user_id, inviter_user_id, status)
                    VALUES (%s, %s, 'pending')
                    ON CONFLICT (referred_user_id) DO NOTHING
                """, (referred_user_id, inviter_user_id))
        except Exception as e:
            logger.error(f"Error registering referral for {referred_user_id}: {e}")
        finally:
            conn.close()

