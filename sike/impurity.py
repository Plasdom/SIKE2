import numpy as np
import os
import json
import post_processing

from transition import *
from atomic_state import State
import core


class Impurity:
    """Impurity class to hold information on the states and transitions for a given modelled impurity species."""

    def __init__(
        self,
        name: str,
        resolve_l: bool,
        resolve_j: bool,
        state_ids: list[int],
        kinetic_electrons: bool,
        maxwellian_electrons: bool,
        saha_boltzmann_init: bool,
        fixed_fraction_init: bool,
        frac_imp_dens: float,
        ionization: bool,
        autoionization: bool,
        emission: bool,
        radiative_recombination: bool,
        excitation: bool,
        collrate_const: float,
        tbrec_norm: float,
        sigma_norm: float,
        time_norm: float,
        T_norm: float,
        n_norm: float,
        vgrid: np.ndarray,
        Egrid: np.ndarray,
        ne: np.ndarray,
        Te: np.ndarray,
    ):
        """Initialise

        :param name: Name of the impurity
        :type name: str
        :param resolve_l: Whether to resolve states by orbital angular momentum quantum number l
        :type resolve_l: bool
        :param resolve_j: Whether to resolve by total angular momentum quantum number j
        :type resolve_j: bool
        :param state_ids: List of state IDs to evolve (default is for all states to be included)
        :type state_ids: list[int]
        :param kinetic_electrons: Whether to solve rate equations for arbitrary electron distributions
        :type kinetic_electrons: bool
        :param maxwellian_electrons: Whether to solve rate equations for Maxwellian electron distributions
        :type maxwellian_electrons: bool
        :param saha_boltzmann_init: Whether to initialise state distribution to Saha-Boltzmann equilibria
        :type saha_boltzmann_init: bool
        :param fixed_fraction_init: Whether to initialise total impurity density to a fixed fraction of the electron density
        :type fixed_fraction_init: bool
        :param frac_imp_dens: Fractional impurity density to initialise (total) impurity densities with, if fixed_fraction_init is True
        :type frac_imp_dens: float
        :param ionization: Whether to include ionization transitions and inverse
        :type ionization: bool
        :param autoionization: Whether to include autoionization transitions
        :type autoionization: bool
        :param emission: Whether to include spontaneous emission transitions
        :type emission: bool
        :param radiative_recombination: Whether to include radiative recombination transitions
        :type radiative_recombination: bool
        :param excitation: Whether to include collisional excitation transitions and inverse
        :type excitation: bool
        :param collrate_const: Collision rate normalisation constant
        :type collrate_const: float
        :param tbrec_norm: Three-body recombination rate normalisation constant
        :type tbrec_norm: float
        :param sigma_norm: Cross-section normalisation constant
        :type sigma_norm: float
        :param time_norm: Time normalisation constant
        :type time_norm: float
        :param T_norm: Temperature normalisation constant
        :type T_norm: float
        :param n_norm: Density normalisation constant
        :type n_norm: float
        :param vgrid: Electron velocity grid
        :type vgrid: np.ndarray
        :param Egrid: Electron energy grid
        :type Egrid: np.ndarray
        :param ne: Electron densities
        :type ne: np.ndarray
        :param Te: Electron temperatures
        :type Te: np.ndarray
        """

        # Save settings
        self.name = name
        self.resolve_j = (resolve_j,)
        self.resolve_l = (resolve_l,)
        self.state_ids = (state_ids,)
        self.kinetic_electrons = (kinetic_electrons,)
        self.maxwellian_electrons = (maxwellian_electrons,)
        self.saha_boltzmann_init = (saha_boltzmann_init,)
        self.fixed_fraction_init = (fixed_fraction_init,)
        self.frac_imp_dens = (frac_imp_dens,)
        self.ionization = (ionization,)
        self.autoionization = (autoionization,)
        self.emission = (emission,)
        self.radiative_recombination = (radiative_recombination,)
        self.excitation = (excitation,)
        self.collrate_const = (collrate_const,)
        self.tbrec_norm = tbrec_norm
        self.sigma_norm = (sigma_norm,)
        self.time_norm = (time_norm,)
        self.T_norm = T_norm
        self.n_norm = n_norm

        # Initialise impurity data
        self.get_element_data()
        print(" Initialising states...")
        self.init_states()
        print(" Initialising transitions...")
        self.init_transitions(vgrid=vgrid, Egrid=Egrid)
        print(" Initialising densities...")
        self.init_dens(ne=ne, Te=Te)
        print(" Finalising states...")
        self.set_state_positions()
        self.set_transition_positions()

    def get_element_data(self):
        """Set the nuclear charge and number of ionisation stages"""
        nuc_chg_dict = {
            "H": 1,
            "He": 2,
            "Li": 3,
            "Be": 4,
            "B": 5,
            "C": 6,
            "N": 7,
            "O": 8,
            "Ne": 10,
            "Ar": 18,
            "W": 74,
        }
        longname_dict = {
            "H": "Hydrogen",
            "He": "Helium",
            "Li": "Lithium",
            "Be": "Beryllium",
            "B": "Boron",
            "C": "Carbon",
            "N": "Nitrogen",
            "O": "Oxygen",
            "Ne": "Neon",
            "Ar": "Argon",
            "W": "Tungsten",
        }
        self.nuc_chg = nuc_chg_dict[self.name]
        self.num_Z = self.nuc_chg + 1
        self.longname = longname_dict[self.name]

    def init_states(self):
        """Initialise the evolved atomic states"""
        if self.resolve_j:
            levels_f = os.path.join(
                os.path.dirname(__file__),
                "atom_data",
                self.longname,
                self.name + "_levels_nlj.json",
            )
        else:
            if self.resolve_l:
                levels_f = os.path.join(
                    os.path.dirname(__file__),
                    "atom_data",
                    self.longname,
                    self.name + "_levels_nl.json",
                )
            else:
                levels_f = os.path.join(
                    os.path.dirname(__file__),
                    "atom_data",
                    self.longname,
                    self.name + "_levels_n.json",
                )
        with open(levels_f) as f:
            levels_dict = json.load(f)
            self.states = [None] * len(levels_dict)
            for i, level_dict in enumerate(levels_dict):
                self.states[i] = State(id=i, **level_dict)

        # Keep only user-specified states
        if self.state_ids is not None:
            for i, state in enumerate(self.states):
                if state.id not in self.state_ids:
                    self.states[i] = None
        self.states = [s for s in self.states if s is not None]

        self.tot_states = len(self.states)

        self.init_ionization_energies()

    def init_ionization_energies(self):
        """Set the ground state levels, ionization energies, delta E from ground state for each atomic state"""

        # Find the lowest energy states
        gs_energies = np.zeros(self.num_Z)
        gs_pos = np.zeros(self.num_Z, dtype=int)
        for Z in range(self.num_Z):
            Z_states = [s for s in self.states if s.Z == Z]
            energies = [s.energy for s in Z_states]
            gs = Z_states[np.argmin(energies)]
            for i, s in enumerate(self.states):
                if s.equals(gs):
                    gs_pos[Z] = i
                    gs_energies[Z] = gs.energy
                    break

        # Mark ground states and calculate ionization energy
        for i in range(len(self.states)):
            if i in gs_pos:
                self.states[i].ground = True
            else:
                self.states[i].ground = False

            if self.states[i].Z < self.num_Z - 1:
                iz_energy = gs_energies[self.states[i].Z + 1] - self.states[i].energy
                self.states[i].iz_energy = iz_energy
            else:
                self.states[i].iz_energy = 0.0

            energy_from_gs = self.states[i].energy - gs_energies[self.states[i].Z]
            self.states[i].energy_from_gs = energy_from_gs

    def init_transitions(
        self,
        vgrid: np.ndarray,
        Egrid: np.ndarray,
    ):
        """Initialise all transitions between evolved atomic states

        :param vgrid: Electron velocity grid
        :type vgrid: np.ndarray
        :param Egrid: Electron energy grid
        :type Egrid: np.ndarray
        """
        if self.resolve_j:
            trans_f = os.path.join(
                os.path.dirname(__file__),
                "atom_data",
                self.longname,
                self.name + "_transitions_nlj.json",
            )
        else:
            if self.resolve_l:
                trans_f = os.path.join(
                    os.path.dirname(__file__),
                    "atom_data",
                    self.longname,
                    self.name + "_transitions_nl.json",
                )
            else:
                trans_f = os.path.join(
                    os.path.dirname(__file__),
                    "atom_data",
                    self.longname,
                    self.name + "_transitions_n.json",
                )
        print("  Loading transitions from json...")
        with open(trans_f) as f:
            trans_dict = json.load(f)
            trans_Egrid = trans_dict[0]["E_grid"]

        print("  Creating transition objects...")
        num_transitions = len(trans_dict)
        transitions = [None] * num_transitions

        for i, trans in enumerate(trans_dict[1:]):
            if self.state_ids is not None:
                if (trans["from_id"] not in self.state_ids) or (
                    trans["to_id"] not in self.state_ids
                ):
                    continue
            if trans["type"] == "ionization" and self.ionization:
                transitions[i] = IzTrans(**trans)
            elif trans["type"] == "autoionization" and self.autoionization:
                transitions[i] = AiTrans(**trans)
            elif (
                trans["type"] == "radiative_recombination"
                and self.radiative_recombination
            ):
                transitions[i] = RRTrans(**trans)
            elif trans["type"] == "emission" and self.emission:
                transitions[i] = EmTrans(**trans)
            elif trans["type"] == "excitation" and self.excitation:
                transitions[i] = ExTrans(**trans)
        transitions = [t for t in transitions if t is not None]

        self.transitions = transitions

        # Set the de-excitation cross-sections
        print("  Creating data for inverse transitions...")
        id2pos = {self.states[i].id: i for i in range(len(self.states))}
        if self.excitation:
            for i, t in enumerate(self.transitions):
                if t.type == "excitation":
                    g_ratio = (
                        self.states[id2pos[t.from_id]].stat_weight
                        / self.states[id2pos[t.to_id]].stat_weight
                    )
                    t.set_sigma_deex(g_ratio, vgrid)

        # Set the statistical weight ratios for ionization cross-sections
        if self.ionization:
            for i, t in enumerate(self.transitions):
                if t.type == "ionization":
                    g_ratio = (
                        self.states[id2pos[t.from_id]].stat_weight
                        / self.states[id2pos[t.to_id]].stat_weight
                    )
                    t.set_inv_data(g_ratio, vgrid)

        # Checks
        print("  Performing checks on transition data...")
        self.state_and_transition_checks(Egrid, trans_Egrid)

    def state_and_transition_checks(self, Egrid: np.ndarray, trans_Egrid: np.ndarray):
        """Perform some checks on states and transitions belonging to the impurity. Removes orphaned states, transitions where one or more associated states are not evolved, etc

        :param Egrid: Default electron energy grid
        :type Egrid: np.ndarray
        :param trans_Egrid: Electron energy grid on which transition rates will be calculated
        :type trans_Egrid: np.ndarray
        :raises ValueError: If the default electron energy grid and the transition energy grid are not the same (will be fixed in future to allow them to differ)
        """

        # Check that simulation E_grid is the same as the transitions E_grid
        if np.max(np.abs(Egrid - trans_Egrid)) > 1e-5:
            # TODO: Handle different energy grids from input to transitions by interpolation
            raise ValueError(
                "Energy grid is different from grid on which transitions evaluated. This will be handled in the future."
            )

        # Check for no orphaned states (i.e. states with either no associated transitions or )
        id2pos = {self.states[i].id: i for i in range(len(self.states))}
        from_ids = np.array([t.from_id for t in self.transitions], dtype=int)
        to_ids = np.array([t.to_id for t in self.transitions], dtype=int)
        for i, state in enumerate(self.states):
            associated_transitions = core.get_associated_transitions(
                state.id, from_ids, to_ids
            )
            if len(associated_transitions) == 0:
                print("State ID " + str(state.id) + " is an orphaned state, removing.")
                self.states[i] = None
                self.tot_states -= 1
        self.states = [s for s in self.states if s is not None]

        # Remove states above ionization energy if no autoionization
        # TODO: Is this necessary?
        if self.autoionization is False:
            for i, state in enumerate(self.states):
                if state.iz_energy < 0:
                    self.states[i] = None
                    self.tot_states -= 1
        self.states = [s for s in self.states if s is not None]

        # Check for no orphaned transitions (i.e. transitions where either from_id or to_id is not evolved)
        state_ids = [s.id for s in self.states]
        for i, trans in enumerate(self.transitions):
            if trans.from_id not in state_ids or trans.to_id not in state_ids:
                self.transitions[i] = None
        self.transitions = [t for t in self.transitions if t is not None]

    def init_dens(
        self,
        ne: np.ndarray,
        Te: np.ndarray,
    ):
        """Initialise densities of impurity states

        :param ne: Electron densities
        :type ne: np.ndarray
        :param Te: Electron temperatures
        :type Te: np.ndarray
        """
        if self.kinetic_electrons:
            self.dens = np.zeros((len(ne), self.tot_states))
        if self.maxwellian_electrons:
            self.dens_Max = np.zeros((len(ne), self.tot_states))

        if self.saha_boltzmann_init:
            self.set_state_positions()

            Z_dens = np.zeros([len(ne), self.num_Z])
            for i in range(len(ne)):
                Z_dens[i, :] = (
                    core.saha_dist(
                        Te[i] * self.T_norm, ne[i] * self.n_norm, self.n_norm, self
                    )
                    / self.n_norm
                )

            for Z in range(self.num_Z):
                Z_states = post_processing.gather_states(self.states, Z)

                energies = [s.energy for s in Z_states]
                stat_weights = [s.stat_weight for s in Z_states]
                locs = [s.pos for s in Z_states]
                for i in range(len(ne)):
                    Z_dens_loc = Z_dens[i, Z]

                    rel_dens = core.boltzmann_dist(
                        Te[i] * self.T_norm, energies, stat_weights, gnormalise=False
                    )

                    if self.kinetic_electrons:
                        self.dens[i, locs] = rel_dens * Z_dens_loc / np.sum(rel_dens)
                        if self.fixed_fraction_init:
                            self.dens[i, locs] *= self.frac_imp_dens * ne[i]
                    if self.maxwellian_electrons:
                        self.dens_Max[i, locs] = (
                            rel_dens * Z_dens_loc / np.sum(rel_dens)
                        )
                        if self.fixed_fraction_init:
                            self.dens_Max[i, locs] *= self.frac_imp_dens * ne[i]
        else:
            if self.fixed_fraction_init:
                if self.kinetic_electrons:
                    self.dens[:, 0] = self.frac_imp_dens * ne
                if self.maxwellian_electrons:
                    self.dens_Max[:, 0] = self.frac_imp_dens * ne

            else:
                if self.kinetic_electrons:
                    self.dens[:, 0] = 1.0
                if self.maxwellian_electrons:
                    self.dens_Max[:, 0] = 1.0

    def set_state_positions(self):
        """Store the positions of each state (which may be different from the state ID)"""
        for i, state in enumerate(self.states):
            self.states[i].pos = i

    def set_transition_positions(self):
        """Store the positions of each from and to state in each transition"""

        id2pos = {}
        for i, state in enumerate(self.states):
            id2pos[state.id] = i

        for i, trans in enumerate(self.transitions):
            self.transitions[i].from_pos = id2pos[self.transitions[i].from_id]
            self.transitions[i].to_pos = id2pos[self.transitions[i].to_id]

    def reorder_PQ_states(self, P_states: str = "ground"):
        """Ensure evolved and non-evolved atomic states are in the correct order

        :param P_states: Which atomic states are evolved, defaults to "ground"
        :type P_states: str, optional
        """
        if P_states == "ground":
            ground_states = [s for s in self.states if s.ground is True]
            other_states = [s for s in self.states if s.ground is False]
            self.num_P_states = len(ground_states)
            self.num_Q_states = len(other_states)
            self.states = ground_states + other_states

        self.set_state_positions()
        self.set_transition_positions()
